from pulp import LpVariable, LpProblem, LpMinimize, lpSum, PULP_CBC_CMD, value, LpStatus
import logging
from typing import Any, Dict, Optional, Tuple
from src.constants import INFEASIBLE_PENALTY, PENALTY_DELAY, DEFAULT_INFRA_ID
from .base_solver import BaseSolver

logger = logging.getLogger(__name__)


class ILPMultiObjectiveSolver(BaseSolver):
    def solve(self, graph_dict: Any, application_set: Any, user_set: Any, 
              config: Dict[str, Any], previous_placement: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Solves the application placement problem using ILP to minimize weighted latency
        for Service Function Chaining (SFC) microservices.
        """
        if config is None:
            config = {}
        infeasible_penalty = float(config.get('setup', {}).get('infeasible_penalty', INFEASIBLE_PENALTY))
        gap_rel = config.get('setup', {}).get('ilp_solver', {}).get('gapRel', 0.05)
        time_limit = config.get('setup', {}).get('ilp_solver', {}).get('timeLimit', 60)

        graph = graph_dict.get_main_graph() 

        if graph is None:
            logger.error("Main graph not found in InfrastructureSet.")
            return None, infeasible_penalty

        graph_item = graph_dict.infrastructures.get(DEFAULT_INFRA_ID, {})
        all_pairs_shortest_paths = graph_item.get('shortest_paths', {})

        applications = application_set.get_all_apps()
        users = user_set.get_all_users()

        active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]
        weights = config.get('setup', {}).get('ilp_solver', {}).get('weights', {})
        latency_weight = weights.get('latency', 1.0)
        migration_weight = weights.get('migration', 100.0)
        server_usage_weight = weights.get('server_usage', 50.0)
        if previous_placement is None:
            previous_placement = {}

        if not active_nodes:
            return None, infeasible_penalty

        # Prepare microservices lists
        # Each app has a list of microservices: [{'id': 'ms0', 'ram': 2.0}, ...]
        ms_indices = []
        for app_id, app_data in applications.items():
            microservices = app_data.get('microservices', [])
            for m_idx, ms in enumerate(microservices):
                ms_indices.append((app_id, ms['id'], m_idx))

        # Decision Variable: x_amn is 1 if microservice 'm' of app 'a' is placed on node 'n'
        x_amn = LpVariable.dicts("Place_MS", 
                                 [(app_id, ms_id, node) for app_id, ms_id, m_idx in ms_indices for node in active_nodes], 
                                 cat='Binary')

        # Decision Variable for SFC links: y_amnn is 1 if source ms is on n1 AND target ms is on n2
        y_amnn = {}
        for app_id, app_data in applications.items():
            edges = app_data.get('edges', [])
            for e_idx, edge in enumerate(edges):
                for n1 in active_nodes:
                    for n2 in active_nodes:
                        y_amnn[(app_id, e_idx, n1, n2)] = LpVariable(f"Link_{app_id}_{e_idx}_{n1}_{n2}", lowBound=0, cat='Continuous')

        prob = LpProblem("SFC_Placement", LpMinimize)
        objective_terms = []

        # 1. User Latency: Delay to the FIRST microservice of the requested app
        for user_id, user_data in users.items():
            requested_app_id = user_data['requestedApp']
            user_home_node = user_data['connectedTo']

            if requested_app_id in applications and user_home_node in active_nodes:
                app_data = applications[requested_app_id]
                if not app_data.get('microservices'):
                    continue
                first_ms_id = app_data['microservices'][0]['id']

                for n in active_nodes:
                    paths_from_user = all_pairs_shortest_paths.get(user_home_node, {})
                    delay_value = paths_from_user.get(n, infeasible_penalty)
                    objective_terms.append(delay_value * user_data['requestRatio'] * x_amn[requested_app_id, first_ms_id, n])

        # 2. Internal SFC Latency: Delay between microservices
        for app_id, app_data in applications.items():
            edges = app_data.get('edges', [])

            # Weight internal delay by the total request ratio for this app
            app_request_ratio = sum(u['requestRatio'] for u in users.values() if u['requestedApp'] == app_id)
            if app_request_ratio == 0:
                app_request_ratio = 1.0 # Give it some base weight so it still optimizes

            for e_idx, edge in enumerate(edges):
                for n1 in active_nodes:
                    paths_from_n1 = all_pairs_shortest_paths.get(n1, {})
                    for n2 in active_nodes:
                        delay_value = paths_from_n1.get(n2, infeasible_penalty)
                        objective_terms.append(delay_value * app_request_ratio * y_amnn[(app_id, e_idx, n1, n2)])

        # 3. Symmetry Breaker: Add a tiny penalty based on node index to break symmetry for apps without users
        # This prevents the solver from getting stuck exploring identical zero-cost placements
        app_idx_map = {app_id: idx for idx, app_id in enumerate(applications.keys())}
        for app_id, ms_id, m_idx in ms_indices:
            a_idx = app_idx_map.get(app_id, 0)
            for node in active_nodes:
                # We use a very small coefficient (e.g. 1e-5 * node) so it doesn't affect real latency decisions
                # but strictly prefers lower-indexed nodes when latency is identical or zero.
                # Convert node to an integer if it's not already, or just use its hash/id
                try:
                    node_idx = int(node)
                except ValueError:
                    node_idx = hash(node) % 1000

                # Break symmetry across both nodes AND identical apps
                sym_penalty = 1e-5 * (node_idx + a_idx * 100)
                objective_terms.append(sym_penalty * x_amn[app_id, ms_id, node])

        latency_cost = lpSum(objective_terms) * latency_weight

        # Migration Cost
        migration_terms = []
        for app_id, ms_id, m_idx in ms_indices:
            # Check if ms_id was placed in previous_placement
            # previous_placement structure: {'App_0': {'0_ms_0': 1, '0_ms_1': 2}, ...}
            prev_node = None
            for app_name, ms_dict in previous_placement.items():
                if ms_id in ms_dict:
                    prev_node = ms_dict[ms_id]
                    break
            if prev_node is not None and prev_node in active_nodes:
                # The cost is 1 if it is placed on ANY node other than prev_node
                # Which is equivalent to (1 - x_amn[...prev_node])
                migration_terms.append(1 - x_amn[app_id, ms_id, prev_node])
        migration_cost = lpSum(migration_terms) * migration_weight

        # Server Usage Cost
        server_usage_terms = []
        z_n = LpVariable.dicts("NodeActive", active_nodes, cat="Binary")
        for node in active_nodes:
            # Big-M constraint: sum(x) <= M * z_n
            # M is the total number of microservices
            M = len(ms_indices)
            prob += lpSum(x_amn[app_id, ms_id, node] for app_id, ms_id, m_idx in ms_indices) <= M * z_n[node], f"Active_{node}"
            server_usage_terms.append(z_n[node])
        server_usage_cost = lpSum(server_usage_terms) * server_usage_weight

        prob += latency_cost + migration_cost + server_usage_cost, "Total_Objective"

        # Constraint 1: Every microservice must be placed exactly once
        for app_id, ms_id, m_idx in ms_indices:
            prob += lpSum(x_amn[app_id, ms_id, node] for node in active_nodes) == 1, f"Placement_{app_id}_{ms_id}"

        # Constraint 2: Generic Resource Capacity constraints per node
        for node in active_nodes:
            node_attrs = graph.nodes[node]
            for attr_name, node_cap in node_attrs.items():
                # We only want numeric capacities
                if isinstance(node_cap, (int, float)):
                    attr_terms = []
                    for app_id, ms_id, m_idx in ms_indices:
                        app_data = applications[app_id]
                        ms_attr_val = app_data['microservices'][m_idx].get(attr_name, 0.0)
                        if ms_attr_val > 0:
                            attr_terms.append(ms_attr_val * x_amn[app_id, ms_id, node])
                    if attr_terms:
                        prob += lpSum(attr_terms) <= node_cap, f"Cap_{attr_name}_{node}"

        # Constraint 3: Linearization of y variables
        for app_id, app_data in applications.items():
            edges = app_data.get('edges', [])
            for e_idx, edge in enumerate(edges):
                ms_id1 = edge['source']
                ms_id2 = edge['target']
                for n1 in active_nodes:
                    # The sum of links originating from ms_id1 on n1 must equal x_amn for ms_id1 on n1
                    prob += lpSum(y_amnn[(app_id, e_idx, n1, n2)] for n2 in active_nodes) == x_amn[app_id, ms_id1, n1], f"Lin3_{app_id}_{e_idx}_{n1}"
                for n2 in active_nodes:
                    # The sum of links terminating at ms_id2 on n2 must equal x_amn for ms_id2 on n2
                    prob += lpSum(y_amnn[(app_id, e_idx, n1, n2)] for n1 in active_nodes) == x_amn[app_id, ms_id2, n2], f"Lin4_{app_id}_{e_idx}_{n2}"

        # Limit solving time to prevent hanging on complex topologies
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=time_limit, gapRel=gap_rel))

        if LpStatus[prob.status] == "Optimal":
            current_objective = value(prob.objective)
            if current_objective >= infeasible_penalty:
                return None, current_objective

            placement = {}

            # Populate placement with microservice-level granularity
            # placement[app_name] = {ms_id: node, ...}
            for app_id, app_data in applications.items():
                app_name = app_data['name']
                placement[app_name] = {}
                for ms in app_data.get('microservices', []):
                    for node in active_nodes:
                        val = value(x_amn[app_id, ms['id'], node])
                        if val is not None and val > 0.5:
                            placement[app_name][ms['id']] = node
                            break
            return placement, current_objective
        else:
            return None, infeasible_penalty


from pulp import LpVariable, LpProblem, LpMinimize, lpSum, PULP_CBC_CMD, value, LpStatus
import logging
from typing import Any, Dict, Optional, Tuple
from src.constants import PENALTY_DELAY, DEFAULT_INFRA_ID
from .base_solver import BaseSolver

logger = logging.getLogger(__name__)


class ILPSingleObjectiveSolver(BaseSolver):
    def solve(self, graph_dict: Any, application_set: Any, user_set: Any, 
              config: Dict[str, Any], previous_placement: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Solves the application placement problem using ILP to minimize weighted latency
        for Service Function Chaining (SFC) microservices.
        """
        if config is None:
            config = {}
        gap_rel = config.get('setup', {}).get('ilp_solver', {}).get('gapRel', 0.05)
        time_limit = config.get('setup', {}).get('ilp_solver', {}).get('timeLimit', 60)

        graph = graph_dict.get_main_graph() 

        if graph is None:
            logger.error("Main graph not found in InfrastructureSet.")
            return None, PENALTY_DELAY

        graph_item = graph_dict.infrastructures.get(DEFAULT_INFRA_ID, {})
        all_pairs_shortest_paths = graph_item.get('shortest_paths', {})

        applications = application_set.get_all_apps()
        users = user_set.get_all_users()

        active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]

        if not active_nodes:
            return None, PENALTY_DELAY

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
                    delay_value = paths_from_user.get(n, PENALTY_DELAY)
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
                        delay_value = paths_from_n1.get(n2, PENALTY_DELAY)
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

        prob += lpSum(objective_terms), "Total_Weighted_Latency"

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
            if current_objective >= PENALTY_DELAY:
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
            return None, PENALTY_DELAY




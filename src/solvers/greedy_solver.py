import logging
from typing import Any, Dict, Optional, Tuple, List
from src.constants import INFEASIBLE_PENALTY, PENALTY_DELAY, DEFAULT_INFRA_ID
from .base_solver import BaseSolver

logger = logging.getLogger(__name__)


class GreedySolver(BaseSolver):
    """
    Algoritmo Greedy para el emplazamiento de microservicios y aplicaciones.
    
    Estrategia del algoritmo:
    1. Ordena todas las aplicaciones desde la más solicitada a la menos solicitada,
       sumando los request rates (requestRatio) de todos los usuarios que solicitan
       una aplicación dada.
    2. Emplaza las aplicaciones en ese orden de prioridad (de mayor a menor solicitud).
    3. Para escoger el nodo donde emplazar una aplicación, busca el punto medio ponderado
       en el grafo de nodos utilizando shortest path hasta los nodos en los que están
       conectados los usuarios que solicitan la aplicación, ponderando por la tasa de
       petición (requestRatio) de cada usuario para atraer el emplazamiento hacia los
       usuarios más activos.
    4. Verifica estrictamente que los recursos utilizados no superen la capacidad
       disponible en cada nodo.
    """

    def solve(
        self,
        graph_dict: Any,
        application_set: Any,
        user_set: Any,
        config: Dict[str, Any],
        previous_placement: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        if config is None:
            config = {}

        infeasible_penalty = float(config.get('setup', {}).get('infeasible_penalty', INFEASIBLE_PENALTY))

        graph = graph_dict.get_main_graph()
        if graph is None:
            logger.error("Main graph not found in InfrastructureSet.")
            return None, infeasible_penalty

        graph_item = graph_dict.infrastructures.get(DEFAULT_INFRA_ID, {})
        all_pairs_shortest_paths = graph_item.get('shortest_paths', {})

        applications = application_set.get_all_apps()
        users = user_set.get_all_users()

        active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]
        if not active_nodes:
            return None, infeasible_penalty

        # 1. Initialize remaining resource capacities per active node
        remaining_resources: Dict[Any, Dict[str, float]] = {}
        for node in active_nodes:
            node_attrs = graph.nodes[node]
            remaining_resources[node] = {}
            for attr_name, node_cap in node_attrs.items():
                if isinstance(node_cap, (int, float)):
                    remaining_resources[node][attr_name] = float(node_cap)

        def can_fit_microservices(node: Any, ms_list: List[Dict[str, Any]]) -> bool:
            demands: Dict[str, float] = {}
            for ms in ms_list:
                for attr_name, demand in ms.items():
                    if isinstance(demand, (int, float)) and demand > 0 and attr_name in remaining_resources[node]:
                        demands[attr_name] = demands.get(attr_name, 0.0) + float(demand)
            for attr_name, total_demand in demands.items():
                if remaining_resources[node].get(attr_name, 0.0) < total_demand:
                    return False
            return True

        def consume_resources(node: Any, ms_list: List[Dict[str, Any]]) -> None:
            for ms in ms_list:
                for attr_name, demand in ms.items():
                    if isinstance(demand, (int, float)) and demand > 0 and attr_name in remaining_resources[node]:
                        remaining_resources[node][attr_name] -= float(demand)

        # Helper for shortest path lookup
        def get_delay(source_node: Any, target_node: Any) -> float:
            if source_node == target_node:
                return 0.0
            paths_from_source = all_pairs_shortest_paths.get(source_node, {})
            return float(paths_from_source.get(target_node, PENALTY_DELAY))

        # 2. Sum request rates per application and map users by requested application
        app_request_rates: Dict[str, float] = {app_id: 0.0 for app_id in applications.keys()}
        app_users_map: Dict[str, List[Dict[str, Any]]] = {app_id: [] for app_id in applications.keys()}

        for user_id, user_data in users.items():
            requested_app_id = user_data.get('requestedApp')
            if requested_app_id in applications:
                app_users_map[requested_app_id].append(user_data)
                app_request_rates[requested_app_id] += float(user_data.get('requestRatio', 0.0))

        # Sort applications from most requested to least requested
        # Tie-breaker: application id ascending for deterministic behavior
        sorted_app_ids = sorted(
            applications.keys(),
            key=lambda app_id: (-app_request_rates.get(app_id, 0.0), str(app_id))
        )

        # Helper to compute weighted median / attraction score of a candidate node for an app's users
        def compute_node_attraction_score(node: Any, app_users: List[Dict[str, Any]]) -> float:
            if not app_users:
                return 0.0
            score = 0.0
            for user_data in app_users:
                user_home_node = user_data.get('connectedTo')
                request_ratio = float(user_data.get('requestRatio', 0.0))
                delay = get_delay(user_home_node, node)
                score += request_ratio * delay
            return score

        # 3. Place applications greedily from most requested to least requested
        placement: Dict[str, Dict[str, Any]] = {}

        for app_id in sorted_app_ids:
            app_data = applications[app_id]
            app_name = app_data['name']
            microservices = app_data.get('microservices', [])
            app_users = app_users_map[app_id]

            # Order candidate nodes by weighted shortest-path score towards active users
            sorted_candidate_nodes = sorted(
                active_nodes,
                key=lambda n: (compute_node_attraction_score(n, app_users), str(n))
            )

            placement[app_name] = {}
            all_placed = False

            # First attempt: place the entire application (all microservices) on the best candidate node
            for candidate_node in sorted_candidate_nodes:
                if can_fit_microservices(candidate_node, microservices):
                    for ms in microservices:
                        placement[app_name][ms['id']] = candidate_node
                    consume_resources(candidate_node, microservices)
                    all_placed = True
                    break

            # Fallback attempt: if no single node can host all microservices, place microservice by microservice
            if not all_placed:
                for ms in microservices:
                    placed_ms = False
                    for candidate_node in sorted_candidate_nodes:
                        if can_fit_microservices(candidate_node, [ms]):
                            placement[app_name][ms['id']] = candidate_node
                            consume_resources(candidate_node, [ms])
                            placed_ms = True
                            break
                    if not placed_ms:
                        logger.warning(
                            f"GreedySolver: Could not place microservice '{ms['id']}' of app '{app_name}' due to resource constraints."
                        )

            # Check if all microservices for this app were placed
            if len(placement[app_name]) < len(microservices):
                logger.warning(
                    f"GreedySolver: Infeasible placement for application '{app_name}'. Not enough resources."
                )
                return None, infeasible_penalty

        # 4. Compute total weighted latency cost matching ILP evaluation
        total_latency = self._compute_total_latency(
            placement, applications, users, active_nodes, all_pairs_shortest_paths, infeasible_penalty
        )
        return placement, total_latency

    def _compute_total_latency(
        self,
        placement: Dict[str, Dict[str, Any]],
        applications: Dict[str, Any],
        users: Dict[str, Any],
        active_nodes: List[Any],
        all_pairs_shortest_paths: Dict[Any, Dict[Any, float]],
        infeasible_penalty: float = INFEASIBLE_PENALTY,
    ) -> float:
        total_latency = 0.0

        def get_delay(source_node: Any, target_node: Any) -> float:
            if source_node == target_node:
                return 0.0
            paths_from_source = all_pairs_shortest_paths.get(source_node, {})
            return float(paths_from_source.get(target_node, infeasible_penalty))

        # 1. User Latency: Delay to the FIRST microservice of the requested app
        for user_id, user_data in users.items():
            requested_app_id = user_data.get('requestedApp')
            user_home_node = user_data.get('connectedTo')

            if requested_app_id in applications and user_home_node in active_nodes:
                app_data = applications[requested_app_id]
                app_name = app_data['name']
                microservices = app_data.get('microservices', [])
                if not microservices:
                    continue
                first_ms_id = microservices[0]['id']

                ms_node = placement.get(app_name, {}).get(first_ms_id)
                if ms_node is not None:
                    delay_value = get_delay(user_home_node, ms_node)
                    total_latency += delay_value * float(user_data.get('requestRatio', 0.0))

        # 2. Internal SFC Latency: Delay between microservices
        for app_id, app_data in applications.items():
            app_name = app_data['name']
            edges = app_data.get('edges', [])

            app_request_ratio = sum(
                float(u.get('requestRatio', 0.0))
                for u in users.values()
                if u.get('requestedApp') == app_id
            )
            if app_request_ratio == 0:
                app_request_ratio = 1.0

            for edge in edges:
                ms_source = edge.get('source')
                ms_target = edge.get('target')
                n1 = placement.get(app_name, {}).get(ms_source)
                n2 = placement.get(app_name, {}).get(ms_target)
                if n1 is not None and n2 is not None:
                    delay_value = get_delay(n1, n2)
                    total_latency += delay_value * app_request_ratio

        return total_latency

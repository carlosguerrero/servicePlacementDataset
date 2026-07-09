import os
import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

from .eventSet import EventSet, init_global_spawner
from .appSet import generate_random_apps
from .factories.graph_factory import generate_infrastructure
from .simulation import (
    SimulationStopped,
    create_simulation_folder,
    save_simulation_step,
    prepare_simulation_data,
    add_and_log_user_count,
    stop_simulation,
)
from .simulationSet import SimulationSet
from .trigger_policies import TriggerPolicyManager
from .target_resolution import resolve_targets


def difference_in_placement(
    old_placement: Optional[Dict[str, Any]],
    new_placement: Optional[Dict[str, Any]],
    old_latency: Optional[float],
    new_latency: Optional[float],
) -> Dict[str, str]:
    """
    Compares old and new application placements and prints information about moved apps.
    old_placement and new_placement are dicts: {app_name: node_id}
    """
    results_dictionary: Dict[str, str] = {}
    moved_apps = []

    if (
        old_placement is None
        or new_placement is None
        or (old_placement == new_placement and old_latency == new_latency)
    ):
        results_dictionary["NO_CHANGES"] = "No changes made."
        logger.debug("APPLICATION PLACEMENT: No changes made.")
        return results_dictionary

    i = 1

    for app_name, old_node in old_placement.items():
        new_node = new_placement.get(app_name)
        if new_node is None:
            moved_apps.append(f"  - App '{app_name}' was removed (was on node {old_node})")
            results_dictionary[f"Change_{i}"] = (
                f"App '{app_name}' was removed (was on node {old_node})"
            )
            i += 1
        elif old_node != new_node:
            moved_apps.append(f"  - App '{app_name}' moved from node {old_node} to node {new_node}")
            results_dictionary[f"Change_{i}"] = (
                f"App '{app_name}' moved from node {old_node} to node {new_node}"
            )
            i += 1

    for app_name, new_node in new_placement.items():
        if app_name not in old_placement:
            moved_apps.append(f"  - App '{app_name}' was newly placed on node {new_node}")
            results_dictionary[f"Change_{i}"] = f"App '{app_name}' was newly placed on node {new_node}"
            i += 1

    if moved_apps or old_latency != new_latency:
        message = ""
        if moved_apps:
            message += "APPLICATION PLACEMENT CHANGES:\n" + "\n".join(moved_apps) + "\n"
        if old_latency != new_latency:
            message += f"Latency changed from {old_latency:.2f} to {new_latency:.2f}"
            results_dictionary["LATENCY"] = (
                f"Changed from {old_latency:.2f} to {new_latency:.2f}"
            )
        logger.info(message.strip())
        return results_dictionary

    results_dictionary["NO_CHANGES"] = "No changes made."
    logger.info("APPLICATION PLACEMENT: No changes made.")
    return results_dictionary


def get_disconnected_apps(placement: Optional[Dict[str, Any]], infrastructure: Any) -> List[str]:
    """Returns a list of apps mapped to disabled nodes."""
    if not placement or not infrastructure:
        return []
    
    graph = infrastructure.get_main_graph()
    if not graph:
        return []
        
    disconnected = set()
    for app_name, ms_placement in placement.items():
        if isinstance(ms_placement, dict):
            for ms_id, node_id in ms_placement.items():
                node_data = graph.nodes.get(node_id, {})
                if not node_data.get('enable', True):
                    disconnected.add(app_name)
        elif isinstance(ms_placement, int) or isinstance(ms_placement, str):
            node_id = ms_placement
            node_data = graph.nodes.get(node_id, {})
            if not node_data.get('enable', True):
                disconnected.add(app_name)
                
    return list(disconnected)

class ServicePlacementSimulation:
    def __init__(
        self,
        config: Dict[str, Any],
        sim_set: SimulationSet,
        total_iterations: int = 500,
    ) -> None:
        self.config = config
        self.sim_set = sim_set
        self.total_iterations = total_iterations

        self.events = EventSet()
        self.infrastructure = None
        self.apps = None
        self.users = None
        self.trigger_manager = TriggerPolicyManager(self.config)
        self.last_opt_placement = None
        self.last_total_latency = None
        self.last_ilp_event_index = 0

    def _compute_total_ram_occupied_percent(self, graph_dict: Any) -> float:
        graph = graph_dict.get_main_graph()
        if graph is None:
            return 0.0

        total_ram = sum(float(feat.get("ram", 0.0)) for _, feat in graph.nodes(data=True))
        if total_ram <= 0:
            return 0.0

        used_ram = sum(float(feat.get("ram_used", 0.0)) for _, feat in graph.nodes(data=True))
        return round((used_ram / total_ram) * 100.0, 2)

    def _build_node_information(self, graph_dict: Any, app_set: Any) -> Dict[str, Any]:
        graph = graph_dict.get_main_graph()
        if graph is None:
            return {}

        node_information: Dict[str, Any] = {}
        for node, feat in graph.nodes(data=True):
            node_key = f"Node_{node}"
            node_information[node_key] = {
                "id": feat.get("id", node),
                "label": feat.get("label", str(node)),
                "layer": feat.get("layer", "edge"),
                "ram": feat.get("ram"),
                "enable": feat.get("enable"),
                "betweenness_centrality": feat.get("betweenness_centrality"),
                "ram_used": feat.get("ram_used"),
                "running_applications": feat.get("running_applications", [])
            }
        return node_information

    def _build_edge_information(self, graph_dict: Any) -> List[Dict[str, Any]]:
        graph = graph_dict.get_main_graph()
        if graph is None:
            return []

        edge_information: List[Dict[str, Any]] = []
        for u, v, attrs in graph.edges(data=True):
            edge_data = {"source": u, "target": v}
            edge_data.update(attrs)
            edge_information.append(edge_data)
        return edge_information

    def _update_system_state(
        self,
        iteration: int,
        sim_folder: str,
        csv_users: str,
        old_opt_placement: Optional[Dict[str, Any]] = None,
        old_total_latency: Optional[float] = None
    ) -> Dict[str, Any]:
        # 1. Get the first event and update the global time
        first_event = self.events.get_first_event()
        if first_event is None:
            raise SimulationStopped("No events available.")

        self.events.global_time = first_event["time"]

        old_node_information = self._build_node_information(self.infrastructure, self.apps)
        old_edge_information = self._build_edge_information(self.infrastructure)
        old_total_ram_occupied = self._compute_total_ram_occupied_percent(self.infrastructure)

        # 2. Save state "before"
        data = prepare_simulation_data(
            {
                "graph": self.infrastructure.get_main_graph(),
                "graph_phase": "before",
                "users": self.users,
                "users_phase": "before",
                "apps": self.apps,
                "apps_phase": "before",
                "placement": old_opt_placement,
                "placement_phase": "before",
                "total_latency": old_total_latency,
                "total_latency_phase": "before",
                "node_information": old_node_information,
                "node_information_phase": "before",
                "edge_information": old_edge_information,
                "edge_information_phase": "before",
                "total_ram_occupied": old_total_ram_occupied,
                "total_ram_occupied_phase": "before",
            }
        )
        save_simulation_step(sim_folder, iteration, data)

        set_map = {
            "user": self.users,
            "app": self.apps,
            "graph": self.infrastructure,
            "graph_node": self.infrastructure,
            "graph_edge": self.infrastructure,
            "global": self, # Global events shouldn't have direct actions unless delegated
        }
        target_object = set_map.get(first_event["type_object"])
        if not target_object and first_event["type_object"] != "global":
            raise ValueError(f"Unknown object type: {first_event['type_object']}")

        # 3. Apply action
        raw_params = first_event.get("impact", {})
        impact_dict = raw_params.copy() if raw_params else {}
        
        composed_of = impact_dict.get("composed_of")
        
        if composed_of and isinstance(composed_of, list):
            messages = []
            executed_details = []
            for sub_action in composed_of:
                sub_action_name = sub_action.get("action_type")
                sub_type = sub_action.get("type_object", first_event.get("type_object", "global"))
                sub_target_object = set_map.get(sub_type)
                if not sub_target_object:
                    continue
                
                sub_params = sub_action.get("impact_params", {}).copy()
                
                # Context injection
                sub_params["config"] = self.config
                sub_params["app_set"] = self.apps
                sub_params["user_set"] = self.users
                sub_params["infrastructure"] = self.infrastructure
                sub_params["sim_set"] = self.sim_set
                sub_params["event_set"] = self.events
                
                targets = resolve_targets(first_event, sub_action, self.apps, self.users, self.infrastructure, self.sim_set)
                
                for target_id in targets:
                    action_method = getattr(sub_target_object, sub_action_name)
                    action_result = action_method(target_id, **sub_params)
                    
                    sub_event_record = {
                        "type_object": sub_type,
                        "object_id": target_id,
                        "action_type": sub_action_name
                    }
                    
                    if isinstance(action_result, str):
                        messages.append(f"[{sub_type}:{target_id}] {action_result}")
                        sub_event_record["message"] = action_result
                    elif isinstance(action_result, dict):
                        if 'message' in action_result:
                            messages.append(f"[{sub_type}:{target_id}] {action_result['message']}")
                        sub_event_record.update(action_result)
                    
                    executed_details.append(sub_event_record)
                        
            first_event["message"] = " | ".join(messages)
            first_event["executed_sub_actions"] = executed_details
            logger.info(f"Processing composite event: {first_event['message']}")
            
        else:
            if not target_object:
                logger.warning(f"No valid target object for action {first_event['action']}")
                first_event["message"] = "Invalid Action Target"
            else:
                params = impact_dict
                params["config"] = self.config
                params["app_set"] = self.apps
                params["user_set"] = self.users
                params["infrastructure"] = self.infrastructure
                params["sim_set"] = self.sim_set
                params["event_set"] = self.events
                
                # Simple events do not go through target_resolution, they use their original object_id
                action_type = first_event.get('action_type', first_event["action"])
                action_method = getattr(target_object, action_type)
                action_result = action_method(first_event.get("object_id"), **params)
                
                if isinstance(action_result, str):
                    first_event["message"] = action_result
                    logger.info(f"Processing event: {action_result}")
                elif isinstance(action_result, dict):
                    first_event.update(action_result)
                    logger.info(f"Processing event: {action_result.get('message', 'Action executed with details')}")

        # 4. Terminal conditions
        # stop_simulation uses exceptions now, so we can exit cleanly.
        stop_simulation(self.apps, self.users, self.infrastructure)

        # 5. Check Trigger Policy to decide if we solve ILP
        should_solve = self.trigger_manager.should_execute_ilp(first_event, self.events.global_time)
        
        if should_solve:
            logger.info(f"ILP Triggered by policy at event {iteration} ({first_event['action']})")
            
            # Use solver factory to get the strategy
            from src.solvers.solver_factory import SolverFactory
            solver = SolverFactory.get_solver(self.config)
            optimal_placement, total_latency = solver.solve(
                self.infrastructure, self.apps, self.users, self.config, previous_placement=self.last_opt_placement
            )
            if optimal_placement:
                self.infrastructure.apply_placement(optimal_placement, self.apps)
                self.last_opt_placement = optimal_placement
                self.last_total_latency = total_latency
            self.last_ilp_event_index = iteration
        else:
            logger.info(f"ILP Skipped by policy at event {iteration}")
            optimal_placement = self.last_opt_placement
            total_latency = self.last_total_latency

        node_information_and_placement_message = self._build_node_information(self.infrastructure, self.apps)
        edge_information_message = self._build_edge_information(self.infrastructure)
        total_ram_occupied = self._compute_total_ram_occupied_percent(self.infrastructure)
        logger.info(f"Total RAM Occupied: {total_ram_occupied}%")

        disconnected_apps = get_disconnected_apps(optimal_placement, self.infrastructure)

        data = prepare_simulation_data(
            {
                "global_time": self.events.global_time,
                "action": first_event,
                "ilp_executed": should_solve,
                "last_ilp_event_index": self.last_ilp_event_index,
                "disconnected_apps": disconnected_apps,
                "placement": optimal_placement,
                "placement_phase": "after",
                "node_information": node_information_and_placement_message,
                "node_information_phase": "after",
                "edge_information": edge_information_message,
                "edge_information_phase": "after",
                "total_latency": total_latency,
                "total_latency_phase": "after",
                "total_ram_occupied": total_ram_occupied,
                "total_ram_occupied_phase": "after",
                "graph": self.infrastructure.get_main_graph(),
                "graph_phase": "after",
                "users": self.users,
                "users_phase": "after",
                "apps": self.apps,
                "apps_phase": "after",
            }
        )
        save_simulation_step(sim_folder, iteration, data)
        add_and_log_user_count(self.users, iteration, csv_users, first_event["action"])

        self.events.update_event_time(
            first_event["id"], self.config, self.sim_set
        )

        return {
            "optimal_placement": optimal_placement,
            "total_latency": total_latency,
        }

    def run(self) -> None:
        # 1) Generate infrastructure, apps, users
        self.infrastructure = generate_infrastructure(self.config, self.events, self.sim_set)

        num_apps = self.config.get("app", {}).get("num_apps")
        saturation_percen = self.config.get("app", {}).get("saturation_percentage")

        self.apps, self.users = generate_random_apps(
            self.config,
            self.events,
            self.sim_set,
            self.infrastructure,
            num_apps=num_apps,
            saturation_percentage=saturation_percen,
        )

        logger.debug("APPS:")
        for app, feat in self.apps.get_all_apps().items():
            logger.debug(
                f"App {app}: name={feat.get('name')}, popularity={feat.get('popularity')}, "
                f"CPU={feat.get('cpu')}, Disk={feat.get('disk')}, RAM={feat.get('ram')}, "
                f"time={feat.get('time_to_run')}"
            )

        logger.debug("USERS:")
        for user_id, user_data in self.users.get_all_users().items():
            logger.debug(
                f"User {user_id}: name={user_data.get('name')}, requestedApp={user_data.get('requestedApp')}, "
                f"appName={user_data.get('appName')}, requestRatio={user_data.get('requestRatio')}, "
                f"connectedTo={user_data.get('connectedTo')}"
            )

        init_global_spawner(self.config, self.events, self.sim_set)
        logger.debug(f"Events: {self.events}")

        # Get initial optimal placement
        from src.solvers.solver_factory import SolverFactory
        solver = SolverFactory.get_solver(self.config)
        optimal_placement, total_latency = solver.solve(
            self.infrastructure, self.apps, self.users, self.config, previous_placement=None
        )
        if optimal_placement:
            self.infrastructure.apply_placement(optimal_placement, self.apps)
            logger.debug(f"Application Placement: {optimal_placement}")
            logger.debug(f"Total Latency: {total_latency}")
            logger.debug("Updated Node Information with Application Placement:")
            actual_graph = self.infrastructure.get_main_graph()
            for node, feat in actual_graph.nodes(data=True):
                logger.debug(
                    f"Node {node}: RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, "
                    f"Running Apps={[self.apps.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}, "
                    f"edges={[f'{nbr} (delay={actual_graph.edges[node, nbr].get('delay', 'N/A')})' for nbr in actual_graph.neighbors(node)]}   "
                )
        else:
            logger.warning("No feasible solution found for application placement.")

        # 3) Run the event-driven iterations
        sim_folder = create_simulation_folder(self.config)
        if sim_folder:
            import shutil
            scenario_path = self.config.get("_scenario_config_path")
            solver_path = self.config.get("_solver_config_path")
            if scenario_path and os.path.exists(scenario_path):
                shutil.copy(scenario_path, os.path.join(sim_folder, os.path.basename(scenario_path)))
            if solver_path and os.path.exists(solver_path):
                shutil.copy(solver_path, os.path.join(sim_folder, os.path.basename(solver_path)))
        
        # Configure FileHandler for DEBUG logs
        file_handler = logging.FileHandler(os.path.join(sim_folder, "execution.log"))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)

        csv_users = os.path.join(sim_folder, "user_counts_log.csv")
        add_and_log_user_count(self.users, 0, csv_users, "No Action")

        # Save step 0
        data = prepare_simulation_data(
            {
                "graph": self.infrastructure.get_main_graph(),
                "graph_phase": "before",
                "users": self.users,
                "users_phase": "before",
                "apps": self.apps,
                "apps_phase": "before",
                "placement": optimal_placement,
                "placement_phase": "after",
                "total_latency": total_latency,
                "total_latency_phase": "after",
                "node_information": self._build_node_information(self.infrastructure, self.apps),
                "node_information_phase": "after",
                "edge_information": self._build_edge_information(self.infrastructure),
                "edge_information_phase": "after",
                "total_ram_occupied": self._compute_total_ram_occupied_percent(self.infrastructure),
                "total_ram_occupied_phase": "after",
            }
        )
        save_simulation_step(sim_folder, 0, data)

        i = 1
        old_opt_placement, old_total_latency = None, None

        try:
            while self.events.events and i < self.total_iterations:
                logger.info(f"--- ITERATION {i} ---")
                actual = self._update_system_state(i, sim_folder, csv_users, old_opt_placement, old_total_latency)
                actual_opt_placement = actual["optimal_placement"]
                actual_total_latency = actual["total_latency"]

                diff_message = difference_in_placement(
                    old_opt_placement,
                    actual_opt_placement,
                    old_total_latency,
                    actual_total_latency,
                )
                data = prepare_simulation_data({"diff_message": diff_message})
                save_simulation_step(sim_folder, i, data)

                old_opt_placement, old_total_latency = (
                    actual_opt_placement,
                    actual_total_latency,
                )
                i += 1
        except SimulationStopped as e:
            logger.info(f"Simulation stopped: {e}")


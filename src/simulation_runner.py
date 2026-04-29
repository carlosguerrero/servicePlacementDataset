import os
from typing import Any, Dict, Optional

from .eventSet import EventSet, init_new_object
from .appSet import generate_random_apps
from .infrastructure import generate_infrastructure
from .simulation import (
    SimulationStopped,
    create_simulation_folder,
    save_simulation_step,
    prepare_simulation_data,
    add_and_log_user_count,
    stop_simulation,
)
from .simulationSet import SimulationSet
from .optimization import solve_application_placement


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
        print("APPLICATION PLACEMENT: No changes made.")
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
        print(message.strip())
        return results_dictionary

    results_dictionary["NO_CHANGES"] = "No changes made."
    print("APPLICATION PLACEMENT: No changes made.")
    return results_dictionary


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

    def _compute_total_ram_occupied_percent(self, graph_dict) -> float:
        graph = graph_dict.get_main_graph()
        if graph is None:
            return 0.0

        total_ram = sum(float(feat.get("ram", 0.0)) for _, feat in graph.nodes(data=True))
        if total_ram <= 0:
            return 0.0

        used_ram = sum(float(feat.get("ram_used", 0.0)) for _, feat in graph.nodes(data=True))
        return round((used_ram / total_ram) * 100.0, 2)

    def _build_node_information(self, graph_dict, app_set) -> Dict[str, str]:
        graph = graph_dict.get_main_graph()
        if graph is None:
            return {}

        node_information: Dict[str, str] = {}
        for node, feat in graph.nodes(data=True):
            node_key = f"Node_{node}"
            running_apps = [
                app_set.get_application(app_id)["name"]
                for app_id in feat.get("running_applications", [])
                if app_set.get_application(app_id) is not None
            ]
            node_information[node_key] = (
                f"RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, "
                f"Running Apps={running_apps}, enabled={feat.get('enable')}"
            )
        return node_information

    def _update_system_state(
        self,
        iteration: int,
        sim_folder: str,
        csv_users: str,
    ) -> Dict[str, Any]:
        # 1. Get the first event and update the global time
        first_event = self.events.get_first_event()
        if first_event is None:
            raise SimulationStopped("No events available.")

        self.events.global_time = first_event["time"]

        # 2. Save state "before"
        data = prepare_simulation_data(
            {
                "graph": self.infrastructure.get_main_graph(),
                "graph_phase": "before",
                "users": self.users,
                "users_phase": "before",
                "apps": self.apps,
                "apps_phase": "before",
            }
        )
        save_simulation_step(sim_folder, iteration, data)

        set_map = {
            "user": self.users,
            "app": self.apps,
            "graph": self.infrastructure,
        }
        target_object = set_map.get(first_event["type_object"])
        if not target_object:
            raise ValueError(f"Unknown object type: {first_event['type_object']}")

        # 3. Apply action
        self.events.update_event_params(
            first_event["id"],
            self.config,
            self.apps,
            self.users,
            self.infrastructure,
            self.sim_set,
        )
        params = first_event["action_params"]
        action_method = getattr(target_object, first_event["action"])
        message = action_method(first_event["object_id"], params)
        if isinstance(message, str):
            first_event["message"] = message
            print("Processing event:", message)

        # 4. Terminal conditions
        # stop_simulation uses exceptions now, so we can exit cleanly.
        stop_simulation(self.apps, self.users, self.infrastructure)

        # 5. Solve and save state "after"
        optimal_placement, total_latency = solve_application_placement(
            self.infrastructure, self.apps, self.users
        )

        node_information_and_placement_message = self._build_node_information(self.infrastructure, self.apps)
        total_ram_occupied = self._compute_total_ram_occupied_percent(self.infrastructure)
        print(f"Total RAM Occupied: {total_ram_occupied}%")

        data = prepare_simulation_data(
            {
                "global_time": self.events.global_time,
                "action": first_event,
                "placement": optimal_placement,
                "node_information": node_information_and_placement_message,
                "total_latency": total_latency,
                "total_ram_occupied": total_ram_occupied,
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

        self.events.update_event_time_and_none_params(
            first_event["id"], self.config, self.sim_set
        )

        return {
            "optimal_placement": optimal_placement,
            "total_latency": total_latency,
        }

    def run(self) -> None:
        # 1) Generate infrastructure, apps, users
        self.infrastructure = generate_infrastructure(self.config, self.events, self.sim_set)

        num_apps = self.config.get("attributes", {}).get("app", {}).get("num_apps")
        saturation_percen = self.config.get("attributes", {}).get("app", {}).get("saturation_percentage")

        self.apps, self.users = generate_random_apps(
            self.config,
            self.events,
            self.sim_set,
            self.infrastructure,
            num_apps=None,
            saturation_percentage=saturation_percen,
        )

        print("\nAPPS:")
        for app, feat in self.apps.get_all_apps().items():
            print(
                f"App {app}: name={feat.get('name')}, popularity={feat.get('popularity')}, "
                f"CPU={feat.get('cpu')}, Disk={feat.get('disk')}, RAM={feat.get('ram')}, "
                f"time={feat.get('time_to_run')}"
            )

        print("\nUSERS:")
        for user_id, user_data in self.users.get_all_users().items():
            print(
                f"User {user_id}: name={user_data.get('name')}, requestedApp={user_data.get('requestedApp')}, "
                f"appName={user_data.get('appName')}, requestRatio={user_data.get('requestRatio')}, "
                f"connectedTo={user_data.get('connectedTo')}, centrality={user_data.get('centrality')}"
            )

        init_new_object(self.config, self.events, self.sim_set)
        print("\nEvents:", self.events)

        # 2) Solve initial ILP (optional output preserved)
        optimal_placement, total_latency = solve_application_placement(
            self.infrastructure, self.apps, self.users
        )
        if optimal_placement:
            print("Application Placement:", optimal_placement)
            print("Total Latency:", total_latency)
            print("\nUpdated Node Information with Application Placement:")
            actual_graph = self.infrastructure.get_main_graph()
            for node, feat in actual_graph.nodes(data=True):
                print(
                    f"Node {node}: RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, "
                    f"Running Apps={[self.apps.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}, "
                    f"edges={[f'{nbr} (delay={actual_graph.edges[node, nbr].get('delay', 'N/A')})' for nbr in actual_graph.neighbors(node)]}   "
                )
        else:
            print("No feasible solution found for application placement.")

        # 3) Run the event-driven iterations
        sim_folder = create_simulation_folder()
        csv_users = os.path.join(sim_folder, "user_counts_log.csv")
        add_and_log_user_count(self.users, 0, csv_users, "No Action")

        # Save step 0
        optimal_placement, total_latency = solve_application_placement(
            self.infrastructure, self.apps, self.users
        )
        data = prepare_simulation_data(
            {
                "graph": self.infrastructure.get_main_graph(),
                "graph_phase": "before",
                "users": self.users,
                "users_phase": "before",
                "apps": self.apps,
                "apps_phase": "before",
                "placement": optimal_placement,
                "total_latency": total_latency,
            }
        )
        save_simulation_step(sim_folder, 0, data)

        i = 1
        old_opt_placement, old_total_latency = None, None

        try:
            while self.events.events and i < self.total_iterations:
                print("\nITERATION", i)
                actual = self._update_system_state(i, sim_folder, csv_users)
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
            print(f"\nSimulation stopped: {e}")


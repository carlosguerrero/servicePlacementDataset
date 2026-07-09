import os
import json
from datetime import datetime
import sys
import networkx as nx  
import csv
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SimulationStopped(Exception):
    """Raised to stop a simulation run when the system reaches a terminal condition."""

def add_and_log_user_count(user_set: Any, i: int, csv_users: str, action: Optional[str]) -> None:
    """
    Writes the latest user count to a CSV after the event has been processed and the system state has been updated.
    """
    new_count = len(user_set.get_all_users())
    file_exists = os.path.isfile(csv_users)
    
    with open(csv_users, mode='a', newline='') as file:
        writer = csv.writer(file)
        
        if not file_exists:
            writer.writerow(['Iteration', 'User Count', 'Action'])
        
        # Write the new row (e.g., Entry 1, 50 users)
        writer.writerow([i, new_count, action if action else 'No Action'])

def create_simulation_folder(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Creates a base 'Simulations_raw' directory and a timestamped subdirectory
    named <scenario_name>_<solver_name>_<timestamp>.
    Returns the path to the specific timestamped folder.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "Simulations_raw"
    scenario_name = config.get("scenario_name", "Sim") if config else "Sim"
    solver_name = config.get("solver_name", "") if config else ""

    if solver_name:
        folder_name = f"{scenario_name}_{solver_name}_{timestamp}"
    elif scenario_name != "Sim":
        folder_name = f"{scenario_name}_{timestamp}"
    else:
        folder_name = f"Sim_{timestamp}"

    full_path = os.path.join(base_dir, folder_name)

    try:
        os.makedirs(full_path, exist_ok=True)
        logger.info(f"Directory created: {full_path}")
        return full_path
    except OSError as e:
        logger.error(f"Error creating directory: {e}")
        return None

def save_simulation_step(folder_path: str, iteration: int, data: Dict[str, Any]) -> None:
    """
    Updates a JSON simulation file by merging new data into the existing JSON object.
    Also optionally saves a NetworkX graph to GML.

    Behavior:
    - If `data` contains keys `_graph_obj` and/or `_graph_phase`, the function
      will use `_graph_obj` as the graph to save as GML and `_graph_phase` as
      the phase tag.
    - The optional `graph_phase` argument overrides any `_graph_phase` in
      `data`.
    """
    graph_obj = None
    graph_phase_from_data = None

    if isinstance(data, dict):
        # Avoid mutating caller-owned dict via `pop()`
        data = dict(data)
        graph_obj = data.pop('graph', None)
        graph_phase_from_data = data.pop('graph_phase', None)

    filename = f"Simulation{iteration}.json"
    file_path = os.path.join(folder_path, filename)

    existing_data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            # If file exists but is empty or corrupted, start with empty dict
            existing_data = {}

    if isinstance(data, dict):
        existing_data.update(data)
    else:
        logger.warning(f"Data for step {iteration} is not a dictionary. Overwriting file.")
        existing_data = data

    try:
        # Open in 'w' (write) mode to overwrite the file with the merged content
        with open(file_path, 'w') as f:
            json.dump(existing_data, f, indent=4) 
    except Exception as e:
        logger.error(f"Error saving step {iteration}: {e}")

    # Disable GML generation as per user request in TODO-list.md
    # if graph_obj is not None:
    #     phase_suffix = graph_phase_from_data if graph_phase_from_data is not None else 'before'
    #     gml_name = f"Simulation{iteration}_graph_{phase_suffix}.gml"
    #     gml_path = os.path.join(folder_path, gml_name)
    #     try:
    #         nx.write_gml(graph_obj, gml_path)
    #     except Exception as e:
    #         logger.error(f"Error saving graph GML for step {iteration}: {e}")

def prepare_graph_data(graph: Optional[nx.Graph], phase: str = 'before') -> Tuple[Optional[nx.Graph], str]:
    """
    Prepares NetworkX graph data for JSON serialization and tags it with a phase.

    Args:
        graph: a NetworkX graph object (or None).
        phase: 'before' or 'after' indicating when the graph was captured.

    Returns:
        A tuple (graph_serializable, graph_obj, phase) where `graph_serializable`
        is suitable for JSON (or {}) and `graph_obj` is the original graph
        (or None) which can be passed to `save_simulation_step` to write a GML file.
    """
    if graph is None:
        return None, phase
    return graph, phase

def prepare_users_data(user_set: Any) -> Dict[str, Any]:
    """
    Prepares user data for JSON serialization.
    Assumes user_set.get_all_users() returns a dict.
    """
    if user_set is None:
        return {}
    users = user_set.get_all_users()
    prepared_users = {}
    for uid, udata in users.items():
        prepared_users[uid] = {k: v for k, v in udata.items() if k != 'actions'}
    return prepared_users

def prepare_apps_data(app_set: Any) -> Any:
    """
    Prepares app data for JSON serialization.
    Assumes app_set.get_all_apps() returns a dict.
    """
    if app_set is None:
        return {}
    apps = app_set.get_all_apps()
    prepared_apps = {}
    for aid, adata in apps.items():
        prepared_apps[aid] = {k: v for k, v in adata.items() if k != 'actions'}
    return prepared_apps

def prepare_action_data(action: Optional[Dict[str, Any]], global_time: Optional[float] = None) -> Dict[str, Any]:
    """
    Prepares action (event) data for JSON serialization.
    Assumes action is a dict (e.g., first_event from update_system_state).
    Includes global_time if provided. Excludes 'impact' to avoid non-serializable objects.
    """
    if action is None:
        return {}
    # Copy the action dict without 'impact' to ensure JSON serializability
    action_without_params = {k: v for k, v in action.items() if k != 'impact'}
    prepared = {'action': action_without_params}
    if global_time is not None:
        prepared['global_time'] = global_time
    return prepared

def prepare_placement_data(placement: Optional[Dict[str, str]]) -> Any:
    """
    Prepares placement data for JSON serialization.
    Assumes placement is a dict (e.g., {'app_name': node}).
    """
    if placement is None:
        return {}
    return placement

def prepare_node_information_and_placement_data(node_information: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Prepares node information and placement data for JSON serialization.
    Assumes node_information is a dict (e.g., {'node_name': {'ram': 100, 'ram_used': 50, 'running_applications': [...]}}).
    """
    if node_information is None:
        return {}
    return node_information

def prepare_difference_in_solutions_data(diff_message: Optional[str]) -> str:
    """
    Returns the changes in between two consecutives solutions of the ILP problem.
    """
    if diff_message is None:
        return ""
    return diff_message

def prepare_total_latency_data(total_latency: Optional[float]) -> float:
    """
    Prepares total latency data for JSON serialization.
    Assumes total_latency is a float or int.
    """
    if total_latency is None:
        return 0.0
    return total_latency    

def prepare_total_ram_occupied_data(total_ram_occupied: Optional[float]) -> float:
    """
    Prepares total RAM occupied data for JSON serialization.
    Assumes total_ram_occupied is a float or int.
    """
    if total_ram_occupied is None:
        return 0.0
    return total_ram_occupied

def prepare_simulation_data(data_sources: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates preparation of simulation data into a single dict based on provided data sources.
    data_sources should be a dict with keys like 'graph', 'users', 'apps', 'action', 'placement', 'total_latency', 'global_time'
    and values as the corresponding objects. 'global_time' is optional and used with 'action'.
    This allows flexible inclusion of only the desired data types.
    
    For 'users' and 'apps', the keys in the output will be dynamically named based on their phase:
    e.g., 'users_before', 'users_after', 'apps_before', 'apps_after'.
    """
    prepared_data = {}
    
    if 'graph' in data_sources:
        graph_phase = data_sources.get('graph_phase', 'before')
        prepared_data['graph'], prepared_data['graph_phase'] = prepare_graph_data(data_sources['graph'], graph_phase)
    
    if 'users' in data_sources:
        users_phase = data_sources.get('users_phase', 'before')
        users_data = prepare_users_data(data_sources['users'])
        prepared_data[f'users_{users_phase}'] = users_data
    
    if 'apps' in data_sources:
        apps_phase = data_sources.get('apps_phase', 'before')
        apps_data = prepare_apps_data(data_sources['apps'])
        prepared_data[f'apps_{apps_phase}'] = apps_data
    
    if 'action' in data_sources:
        global_time = data_sources.get('global_time')
        prepared_data['action'] = prepare_action_data(data_sources['action'], global_time)
    
    if 'placement' in data_sources:
        phase = data_sources.get('placement_phase', 'after')
        prepared_data[f'placement_{phase}'] = prepare_placement_data(data_sources['placement'])

    if 'node_information' in data_sources:
        phase = data_sources.get('node_information_phase', 'after')
        prepared_data[f'node_information_{phase}'] = prepare_node_information_and_placement_data(data_sources['node_information'])

    if 'edge_information' in data_sources:
        phase = data_sources.get('edge_information_phase', 'after')
        prepared_data[f'edge_information_{phase}'] = data_sources['edge_information']

    if 'ilp_executed' in data_sources:
        prepared_data['ilp_executed'] = data_sources['ilp_executed']
        
    if 'last_ilp_event_index' in data_sources:
        prepared_data['last_ilp_event_index'] = data_sources['last_ilp_event_index']
        
    if 'disconnected_apps' in data_sources:
        prepared_data['disconnected_apps'] = data_sources['disconnected_apps']

    if 'diff_message' in data_sources:
        prepared_data['diff_message'] = prepare_placement_data(data_sources['diff_message'])

    if 'total_latency' in data_sources:
        phase = data_sources.get('total_latency_phase', 'after')
        prepared_data[f'total_latency_{phase}'] = prepare_total_latency_data(data_sources['total_latency'])
    
    if 'total_ram_occupied' in data_sources:
        phase = data_sources.get('total_ram_occupied_phase', 'after')
        prepared_data[f'total_ram_occupied_{phase}'] = prepare_total_ram_occupied_data(data_sources['total_ram_occupied'])
    
    return prepared_data

def stop_simulation(app_set: Any, user_set: Any, graph_dict: Any) -> None:
    """
    Stop the program in case apps, users, active nodes or active edges is empty
    """
    if not app_set.get_all_apps():
        logger.info("STOPPING THE SIMULATION: No applications available after processing the event.")
        raise SimulationStopped("No applications available after processing the event.")
    if not user_set.get_all_users():
        logger.info("STOPPING THE SIMULATION: No users available after processing the event.")
        raise SimulationStopped("No users available after processing the event.")
    active_nodes = graph_dict.get_active_nodes()
    if not active_nodes:
        logger.info("STOPPING THE SIMULATION: No active nodes in the graph after processing the event.")
        raise SimulationStopped("No active nodes in the graph after processing the event.")
    active_edges = graph_dict.get_active_edges()
    if not active_edges:
        logger.info("STOPPING THE SIMULATION: No active edges in the graph after processing the event.")
        raise SimulationStopped("No active edges in the graph after processing the event.")
import os
import json
from datetime import datetime
import networkx as nx  

def create_simulation_folder():
    """
    Creates a base 'Simulations' directory and a timestamped subdirectory.
    Returns the path to the specific timestamped folder.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "Simulations"
    folder_name = f"Sim_{timestamp}"
    
    full_path = os.path.join(base_dir, folder_name)
    
    try:
        os.makedirs(full_path, exist_ok=True)
        print(f"Directory created: {full_path}")
        return full_path
    except OSError as e:
        print(f"Error creating directory: {e}")
        return None

def save_simulation_step(folder_path, iteration, data):
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
        print(f"Warning: Data for step {iteration} is not a dictionary. Overwriting file.")
        existing_data = data

    try:
        # Open in 'w' (write) mode to overwrite the file with the merged content
        with open(file_path, 'w') as f:
            json.dump(existing_data, f, indent=4) 
        # print(f"Updated data in: {filename}")
    except Exception as e:
        print(f"Error saving step {iteration}: {e}")

    if graph_obj is not None:
        phase_suffix = graph_phase_from_data if graph_phase_from_data is not None else 'before'
        gml_name = f"Simulation{iteration}_graph_{phase_suffix}.gml"
        gml_path = os.path.join(folder_path, gml_name)
        try:
            nx.write_gml(graph_obj, gml_path)
            # print(f"Saved graph GML: {gml_name}")
        except Exception as e:
            print(f"Error saving graph GML for step {iteration}: {e}")

def prepare_graph_data(graph, phase='before'):
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

def prepare_users_data(user_set):
    """
    Prepares user data for JSON serialization.
    Assumes user_set.get_all_users() returns a dict.
    """
    if user_set is None:
        return {}
    return user_set.get_all_users()

def prepare_apps_data(app_set):
    """
    Prepares app data for JSON serialization.
    Assumes app_set.get_all_apps() returns a dict.
    """
    if app_set is None:
        return {}, None
    return app_set.get_all_apps()

def prepare_action_data(action, global_time=None):
    """
    Prepares action (event) data for JSON serialization.
    Assumes action is a dict (e.g., first_event from update_system_state).
    Includes global_time if provided. Excludes 'action_params' to avoid non-serializable objects.
    """
    if action is None:
        return {}
    # Copy the action dict without 'action_params' to ensure JSON serializability
    action_without_params = {k: v for k, v in action.items() if k != 'action_params'}
    prepared = {'action': action_without_params}
    if global_time is not None:
        prepared['global_time'] = global_time
    return prepared

def prepare_placement_data(placement):
    """
    Prepares placement data for JSON serialization.
    Assumes placement is a dict (e.g., {'app_name': node}).
    """
    if placement is None:
        return {}
    return placement

def prepare_node_information_and_placement_data(node_information):
    """
    Prepares node information and placement data for JSON serialization.
    Assumes node_information is a dict (e.g., {'node_name': {'ram': 100, 'ram_used': 50, 'running_applications': [...]}}).
    """
    if node_information is None:
        return {}
    return node_information

def prepare_total_latency_data(total_latency):
    """
    Prepares total latency data for JSON serialization.
    Assumes total_latency is a float or int.
    """
    if total_latency is None:
        return 0.0
    return total_latency    

def prepare_simulation_data(data_sources):
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
        prepared_data['placement'] = prepare_placement_data(data_sources['placement'])

    if 'node_information' in data_sources:
        prepared_data['node_information'] = prepare_node_information_and_placement_data(data_sources['node_information'])

    if 'total_latency' in data_sources:
        prepared_data['total_latency'] = prepare_total_latency_data(data_sources['total_latency'])
    
    return prepared_data

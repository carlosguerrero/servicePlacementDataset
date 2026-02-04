import os
import json
from datetime import datetime
import networkx as nx  

import random # Imported just to generate data for the example

def create_simulation_folder():
    """
    Creates a base 'Simulations' directory and a timestamped subdirectory.
    Returns the path to the specific timestamped folder.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = "Simulations"
    folder_name = f"Sim_{timestamp}"
    
    # Create the full path: Simulations/Sim_20231027_103000
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
    Appends simulation data to a .txt file in JSON format.
    If the file exists, it appends; if not, it creates it.
    """
    filename = f"Simulation{iteration}.txt"
    file_path = os.path.join(folder_path, filename)
    
    try:
        # 'a' mode opens for appending. Creates the file if it doesn't exist.
        with open(file_path, 'a') as f:
            json_string = json.dumps(data)
            f.write(json_string + "\n")
            
        print(f"Appended data to: {filename}")
        
    except Exception as e:
        print(f"Error saving step {iteration}: {e}")

def prepare_graph_data(graph):
    """
    Prepares NetworkX graph data for JSON serialization.
    Returns a dict with nodes, edges, and attributes.
    """
    if graph is None:
        return {}
    return nx.node_link_data(graph)

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
        return {}
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
    """
    prepared_data = {}
    
    if 'graph' in data_sources:
        prepared_data['graph'] = prepare_graph_data(data_sources['graph'])
    
    if 'users' in data_sources:
        prepared_data['users'] = prepare_users_data(data_sources['users'])
    
    if 'apps' in data_sources:
        prepared_data['apps'] = prepare_apps_data(data_sources['apps'])
    
    if 'action' in data_sources:
        global_time = data_sources.get('global_time')
        prepared_data['action'] = prepare_action_data(data_sources['action'], global_time)
    
    if 'placement' in data_sources:
        prepared_data['placement'] = prepare_placement_data(data_sources['placement'])

    if 'total_latency' in data_sources:
        prepared_data['total_latency'] = prepare_total_latency_data(data_sources['total_latency'])
    
    return prepared_data

# --- Example Usage Logic ---

def run_simulation():
    # 1. Setup the folder structure once before the loop starts
    sim_folder = create_simulation_folder()
    
    if not sim_folder:
        return # Stop if folder creation failed

    # 2. Run the Simulation Loop
    total_iterations = 5
    
    for i in range(total_iterations):
        # --- Your Simulation Logic Here ---
        # Creating dummy data to represent simulation state
        current_state = {
            "step": i,
            "temperature": 20 + (i * 1.5),
            "pressure": random.uniform(100, 105),
            "particles": [
                {"id": 1, "x": random.random(), "y": random.random()},
                {"id": 2, "x": random.random(), "y": random.random()}
            ]
        }
        # ----------------------------------

        # 3. Save the specific step
        save_simulation_step(sim_folder, i, current_state)

# Execute the example
if __name__ == "__main__":
    run_simulation()
import yaml
import random
import uuid
import networkx as nx
from pulp import *
import pickle
import os
from datetime import datetime
import sys
import csv
import numpy as np

from src import EventSet, generate_events, init_new_object, ApplicationSet, generate_random_apps, UserSet, generate_random_users, generate_infrastructure
from src.simulationSet import SimulationSet
from src import create_simulation_folder, save_simulation_step, prepare_simulation_data, add_and_log_user_count, stop_simulation
from src.utils.auxiliar_functions import get_random_from_range

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

# BORRAR: versión original de Carlos
def solve_application_placement_carlos(graph, application_set, user_set):
    """Solves the application placement problem using ILP."""
    applications = application_set.get_all_apps()
    nodes = list(graph.nodes())
    users = user_set.get_all_users()

    # Pre-calculate all-pairs shortest paths based on 'delay'
    # This is crucial for efficient latency calculation in the objective function
    try:
        # Check if the graph is connected. If not, shortest_path_length might fail for some pairs.
        # For disconnected graphs, consider infinite delay or a large penalty.
        # Here, we assume connectivity for all relevant pairs.
        all_pairs_shortest_paths = dict(nx.all_pairs_dijkstra_path_length(graph, weight='delay'))
    except nx.NetworkXNoPath:
        print("Warning: Graph is disconnected. Some shortest paths might not exist.")
        # Handle disconnected components if necessary, e.g., by assigning a very large delay
        all_pairs_shortest_paths = {} # Fallback

    # Decision variable: Is application 'a' placed on node 'n'? (Binary: 0 = no, 1 = yes)
    x_an = LpVariable.dicts("Place", [(app_id, node) for app_id in applications for node in nodes], cat='Binary')

    # Objective function: Minimize the total weighted latency
    prob = LpProblem("Application_Placement", LpMinimize)

    # The objective is built directly using the pre-calculated shortest paths
    objective_terms = []
    for user_id, user_data in users.items():
        requested_app_id = user_data['requestedApp']
        user_home_node = user_data['connectedTo']

        if requested_app_id and user_home_node is not None:
            # Sum over all possible placement nodes for the requested app
            # Only one x_an for a given requested_app_id will be 1
            for node_app_placed in nodes:
                # Get the delay from the user's home node to the node where the app is placed
                delay_value = all_pairs_shortest_paths.get(user_home_node, {}).get(node_app_placed, float('inf'))
                # Add term: (delay * request_ratio * x_an)
                objective_terms.append(delay_value * user_data['requestRatio'] * x_an[requested_app_id, node_app_placed])
        
    prob += lpSum(objective_terms), "Total Weighted Latency"

    # Constraint 1: Each application is placed on exactly one node
    for app_id in applications:
        prob += lpSum(x_an[app_id, node] for node in nodes) == 1, f"PlacementConstraint_{app_id}"

    # Constraint 2: Total RAM used on a node does not exceed its capacity
    for node in nodes:
        prob += lpSum(applications[app_id]['ram'] * x_an[app_id, node] for app_id in applications) <= graph.nodes[node]['ram'], f"RAMConstraint_{node}"

    # Solve the ILP problem
    prob.solve(PULP_CBC_CMD(msg=0)) # msg=0 to suppress solver output

    if LpStatus[prob.status] == "Optimal":
        print("\nOptimal Application Placement Found:")
        placement = {}
        total_ram_used_per_node = {node: 0.0 for node in nodes}
        for app_id, app_data in applications.items():
            for node in nodes:
                if value(x_an[app_id, node]) == 1:
                    placement[app_data['name']] = node
                    total_ram_used_per_node[node] += app_data['ram']
                    break

        # Update the graph nodes with the placement information
        #for node in nodes:
        #    graph.nodes[node]['running_applications'] = [] # Reset before updating
        #    graph.nodes[node]['ram_used'] = 0.0 # Reset before updating

        #for app_id, app_data in applications.items():
        #    for node in nodes:
        #        if value(x_an[app_id, node]) == 1:
        #            graph.nodes[node]['running_applications'].append(app_id)
        #            graph.nodes[node]['ram_used'] += app_data['ram'] # Already accumulated in total_ram_used_per_node, but update node attribute

        return placement, value(prob.objective)
    else:
        print(f"No Optimal Solution Found. Status: {LpStatus[prob.status]}")
        return None, None

def solve_application_placement(graph_dict, application_set, user_set):
    PENALTY_DELAY = 1_000_000 
    graph = graph_dict.get_main_graph() 

    if graph is None:
        print("Error: Main graph not found in InfrastructureSet.")
        return None, PENALTY_DELAY

    graph_item = graph_dict.infrastructures.get('000', {})
    all_pairs_shortest_paths = graph_item.get('shortest_paths', {})

    applications = application_set.get_all_apps()
    users = user_set.get_all_users()
    
    active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]

    if not active_nodes:
        return None, PENALTY_DELAY

    # Decision Variable
    x_an = LpVariable.dicts("Place", [(app_id, node) for app_id in applications for node in active_nodes], cat='Binary')

    prob = LpProblem("Application_Placement", LpMinimize)
    objective_terms = []

    for user_id, user_data in users.items():
        requested_app_id = user_data['requestedApp']
        user_home_node = user_data['connectedTo']

        if requested_app_id and user_home_node in active_nodes:
            for node_app_placed in active_nodes:
                # OPTIMIZATION: Direct lookup in the cached dictionary
                paths_from_user = all_pairs_shortest_paths.get(user_home_node, {})
                delay_value = paths_from_user.get(node_app_placed, PENALTY_DELAY)
                
                objective_terms.append(delay_value * user_data['requestRatio'] * x_an[requested_app_id, node_app_placed])
        
    prob += lpSum(objective_terms), "Total Weighted Latency"

    # Constraint 1: Placement
    for app_id in applications:
        prob += lpSum(x_an[app_id, node] for node in active_nodes) == 1, f"PlacementConstraint_{app_id}"

    # Constraint 2: RAM
    for node in active_nodes:
        prob += lpSum(applications[app_id]['ram'] * x_an[app_id, node] for app_id in applications) <= graph.nodes[node]['ram'], f"RAMConstraint_{node}"

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == "Optimal":
        current_objective = value(prob.objective)
        if current_objective >= PENALTY_DELAY:
            return None, current_objective

        placement = {}
        # Initialize node attributes for tracking ram_used and running_applications
        for node in active_nodes:
            graph.nodes[node]['ram_used'] = 0.0
            graph.nodes[node]['running_applications'] = []
        
        # Populate placement and update node attributes
        for app_id, app_data in applications.items():
            for node in active_nodes:
                if value(x_an[app_id, node]) == 1:
                    placement[app_data['name']] = node
                    graph.nodes[node]['ram_used'] += app_data['ram']
                    graph.nodes[node]['running_applications'].append(app_id)
                    break
        return placement, current_objective
    else:
        return None, PENALTY_DELAY
    
def difference_in_placement(old_placement, new_placement, old_latency, new_latency):
    """
    Compares old and new application placements and prints information about moved apps.
    old_placement and new_placement are dicts: {app_name: node_id}
    """
    results_dictionary = {}
    moved_apps = []

    # If everything is identical (or missing), return immediately
    if old_placement is None or new_placement is None or (old_placement == new_placement and old_latency == new_latency):
        results_dictionary["NO_CHANGES"] = "No changes made."
        print("APPLICATION PLACEMENT: No changes made.")
        return results_dictionary
    
    i = 1
    # Check for apps that moved or were removed
    for app_name, old_node in old_placement.items():
        new_node = new_placement.get(app_name)
        if new_node is None:
            moved_apps.append(f"  - App '{app_name}' was removed (was on node {old_node})")
            change_key = f"Change_{i}"
            results_dictionary[change_key] = f"App '{app_name}' was removed (was on node {old_node})"
            i += 1
        elif old_node != new_node:
            moved_apps.append(f"  - App '{app_name}' moved from node {old_node} to node {new_node}")
            change_key = f"Change_{i}"
            results_dictionary[change_key] = f"App '{app_name}' moved from node {old_node} to node {new_node}"
            i += 1
    
    # Check for newly placed apps
    for app_name, new_node in new_placement.items():
        if app_name not in old_placement:
            moved_apps.append(f"  - App '{app_name}' was newly placed on node {new_node}")
            change_key = f"Change_{i}"
            results_dictionary[change_key] = f"App '{app_name}' was newly placed on node {new_node}"
            i += 1
    
    # Output the changes if placement OR latency changed
    if moved_apps or old_latency != new_latency:
        message = ""
        
        if moved_apps:
            message += "APPLICATION PLACEMENT CHANGES:\n" + "\n".join(moved_apps) + "\n"
        
        if old_latency != new_latency:
            message += f"Latency changed from {old_latency:.2f} to {new_latency:.2f}"
            results_dictionary["LATENCY"] = f"Changed from {old_latency:.2f} to {new_latency:.2f}"
            
        print(message.strip())
        return results_dictionary
    else:
        # Fallback if somehow we get here with no changes
        results_dictionary["NO_CHANGES"] = "No changes made."
        print("APPLICATION PLACEMENT: No changes made.")
        return results_dictionary

def update_system_state(events_list, config, app_set, user_set, graph_dict, iteration, sim_folder, sim_set, csv_users):
    # 1. Get the first event and update the global time
    first_event = events_list.get_first_event()
    events_list.global_time = first_event['time']

    # 2. Prepare and save the state "before" before processing the event
    data = prepare_simulation_data({
        'graph': graph_dict.get_main_graph(),
        'graph_phase': 'before',
        'users': user_set,
        'users_phase': 'before',
        'apps': app_set, 
        'apps_phase': 'before'
    })
    save_simulation_step(sim_folder, iteration, data)
    
    # 3. Identify which set we need to update based on 'type_object': user, app, graph
    set_map = {
        'user': user_set,
        'app': app_set,
        'graph': graph_dict
    }
    target_object = set_map.get(first_event['type_object'])
    if not target_object:
        raise ValueError(f"Unknown object type: {first_event['type_object']}")
    
    # 4. Apply the action method to update the state of the system
    events_list.update_event_params(first_event['id'], config, app_set, user_set, graph_dict, sim_set)
    params = first_event['action_params']
    action_method = getattr(target_object, first_event['action'])
    message = action_method(first_event['object_id'], params)
    if isinstance(message, str):
        first_event['message'] = message
        print("Processing event:", message)

    stop_simulation(app_set, user_set, graph_dict)
    
    # 5. Prepare and save the state "after" after processing the event
    # DESCOMENTAR: optimal_placement, total_latency = solve_application_placement(graph_dict, app_set, user_set)
    optimal_placement, total_latency = 0, 0

    node_information_and_placement_message = {}
    for node, feat in graph_dict.get_main_graph().nodes(data=True):
        node_key = f"Node_{node}"
        node_information_and_placement_message[node_key] = f"RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, Running Apps={[app_set.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}, enabled={feat.get('enable')}"

    total_ram_occupied = round((sum(feat.get('ram_used', 0.0) for _, feat in graph_dict.get_main_graph().nodes(data=True)) / sum(feat.get('ram', 0.0) for _, feat in graph_dict.get_main_graph().nodes(data=True)) if sum(feat.get('ram', 0.0) for _, feat in graph_dict.get_main_graph().nodes(data=True)) > 0 else 0)*100, 2)
    print(f"Total RAM Occupied: {total_ram_occupied}%")

    data = prepare_simulation_data({
        'global_time': events_list.global_time,
        'action': first_event,
        'placement': optimal_placement,
        'node_information': node_information_and_placement_message,
        'total_latency': total_latency,
        'total_ram_occupied': total_ram_occupied,
        'graph': graph_dict.get_main_graph(),
        'graph_phase': 'after',
        'users': user_set,
        'users_phase': 'after',
        'apps': app_set,
        'apps_phase': 'after'
    })
    save_simulation_step(sim_folder, iteration, data)
    add_and_log_user_count(user_set, iteration, csv_users, first_event['action'])

    events_list.update_event_time_and_none_params(first_event['id'], config, sim_set)

    return optimal_placement, total_latency
    
def generate_scenario(events_list, config, app_set, user_set, graph_dict, sim_set):
    sim_folder = create_simulation_folder()
    csv_users = os.path.join(sim_folder, "user_counts_log.csv")
    add_and_log_user_count(user_set, 0, csv_users, "No Action")

    # Calculate first scenario and save it in the iteration_0
    optimal_placement, total_latency = solve_application_placement(graph_dict, app_set, user_set)
    print("SOLUTION ILP of application placement:", optimal_placement)

    data = prepare_simulation_data({
        'graph': graph_dict.get_main_graph(),
        'graph_phase': 'before',
        'users': user_set,
        'users_phase': 'before',
        'apps': app_set, 
        'apps_phase': 'before',
        'placement': optimal_placement, 
        'total_latency': total_latency
    })
    save_simulation_step(sim_folder, 0, data)

    total_iterations = 500
    i = 1
    old_opt_placement, old_total_latency = None, None
    while events_list.events and i < total_iterations: # and global_time < 300
        print("\nITERATION", i)
        actual_opt_placement, actual_total_latency = update_system_state(events_list, config, app_set, user_set, graph_dict, i, sim_folder, sim_set, csv_users)
        diff_message = difference_in_placement(old_opt_placement, actual_opt_placement, old_total_latency, actual_total_latency)
        data = prepare_simulation_data({'diff_message': diff_message})
        save_simulation_step(sim_folder, i, data)
        old_opt_placement, old_total_latency = actual_opt_placement, actual_total_latency
        i += 1

def main():
    sim_set = SimulationSet(master_seed=42)

    # If we want MANUAL GENERATION OF GRAPH -> config_manual = "config_manual.yaml"
    config_random = "config_random.yaml"
    config = load_config(config_random)

    generated_events = EventSet()

    # RANDOM GENERATION OF GRAPH
    generated_infrastructure = generate_infrastructure(config, generated_events, sim_set)
    actual_graph = generated_infrastructure.get_main_graph() 

    num_apps = config.get('attributes', {}).get('app', {}).get('num_apps')
    saturation_percen = config.get('attributes', {}).get('app', {}).get('saturation_percentage')
    # BORRAR: generated_apps = generate_random_apps(config, generated_events, sim_set)
    generated_apps, generated_users = generate_random_apps(config, generated_events, sim_set, generated_infrastructure, num_apps=None, saturation_percentage=saturation_percen)
    print("\nAPPS:")
    for app, feat in generated_apps.get_all_apps().items():
        print(f"App {app}: name={feat.get('name')}, popularity={feat.get('popularity')}, CPU={feat.get('cpu')}, Disk={feat.get('disk')}, RAM={feat.get('ram')}, time={feat.get('time_to_run')}")

    print("\nUSERS:")
    for user_id, user_data in generated_users.get_all_users().items():
        print(f"User {user_id}: name={user_data.get('name')}, requestedApp={user_data.get('requestedApp')}, appName={user_data.get('appName')}, requestRatio={user_data.get('requestRatio')}, connectedTo={user_data.get('connectedTo')}, centrality={user_data.get('centrality')}")

    init_new_object(config, generated_events, sim_set)

    print("\nEvents:", generated_events)

    # SOLVE PROBLEM
    if generated_apps and generated_users and generated_infrastructure:
        optimal_placement, total_latency = solve_application_placement(generated_infrastructure, generated_apps, generated_users)
        if optimal_placement:
            print("Application Placement:", optimal_placement)
            print("Total Latency:", total_latency)
            print("\nUpdated Node Information with Application Placement:")
            for node, feat in actual_graph.nodes(data=True):
                print(f"Node {node}: RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, Running Apps={[generated_apps.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}, edges={[f'{nbr} (delay={actual_graph.edges[node, nbr].get('delay', 'N/A')})' for nbr in actual_graph.neighbors(node)]}   ")
        else:
            print("No feasible solution found for application placement.")
    
    # WORKING ON ITERATIONS
    print("\n---- EVENTS ----")
    generate_scenario(generated_events, config, generated_apps, generated_users, generated_infrastructure, sim_set)


if __name__ == "__main__":
    main()
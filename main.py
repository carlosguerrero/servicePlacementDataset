import yaml
import random
import uuid
import networkx as nx
from pulp import *
import pickle
import os
from datetime import datetime
import sys

from src import EventSet, generate_events, init_new_object, ApplicationSet, generate_random_apps, UserSet, generate_random_users, generate_infrastructure
from src import create_simulation_folder, save_simulation_step, prepare_simulation_data
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

def update_system_state(events_list, config, app_set, user_set, graph_dict, iteration, sim_folder):

    first_event = events_list.get_first_event()
    events_list.global_time = first_event['time']

    data = prepare_simulation_data({
        'graph': graph_dict.get_main_graph(),
        'graph_phase': 'before',
        'users': user_set,
        'users_phase': 'before',
        'apps': app_set, 
        'apps_phase': 'before'
    })
    save_simulation_step(sim_folder, iteration, data)
    
    # Identify which set we need to update based on 'type_object': user, app, graph
    set_map = {
        'user': user_set,
        'app': app_set,
        'graph': graph_dict
    }
    target_object = set_map.get(first_event['type_object'])
    if not target_object:
        raise ValueError(f"Unknown object type: {first_event['type_object']}")
    
    events_list.update_event_params(first_event['id'], config, app_set, user_set, graph_dict)
    params = first_event['action_params']

    print("Time event:", first_event['time'])
    action_method = getattr(target_object, first_event['action'])
    message = action_method(first_event['object_id'], params)

    # If the action returned a human-readable message, save it in the event
    if isinstance(message, str):
        first_event['message'] = message
        print("Processing event:", message)
    
    # Stop the program in case apps, users, active nodes or active edges is empty
    if not app_set.get_all_apps():
        print("STOPPING THE SIMULATION:  No applications available after processing the event. Stopping the simulation.")
        sys.exit()
    if not user_set.get_all_users():
        print("STOPPING THE SIMULATION:  No users available after processing the event.")
        sys.exit()
    # BORRAR: tengo que añadir lo de active_nodes
    # active_nodes = graph_dict.get_active_nodes()
    # if not active_nodes:
    #     print("No active nodes in the graph after processing the event. Stopping the simulation.")
    #     sys.exit()
    # active_edges = graph_dict.get_active_edges()
    # if not active_edges:
    #     print("No active edges in the graph after processing the event. Stopping the simulation.")
    #     sys.exit()

    optimal_placement, total_latency = solve_application_placement(graph_dict, app_set, user_set)

    node_information_and_placement_message = ""
    for node, feat in graph_dict.get_main_graph().nodes(data=True):
        # print(f"Node {node}: RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, Running Apps={[app_set.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}")
        node_information_and_placement_message += f"Node {node}: RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, Running Apps={[app_set.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}\n"

    data = prepare_simulation_data({
        'global_time': events_list.global_time,
        'action': first_event,
        'placement': optimal_placement,
        'node_information': node_information_and_placement_message,
        'total_latency': total_latency,
        'graph': graph_dict.get_main_graph(),
        'graph_phase': 'after',
        'users': user_set,
        'users_phase': 'after',
        'apps': app_set,
        'apps_phase': 'after'
    })
    save_simulation_step(sim_folder, iteration, data)

    events_list.update_event_time_and_none_params(first_event['id'], config)
    
def generate_scenario(events_list, config, app_set, user_set, graph_dict):
    sim_folder = create_simulation_folder()

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

    total_iterations = 20
    i = 1
    while events_list.events and i < total_iterations: # and global_time < 300
        print("\nITERATION", i)
        update_system_state(events_list, config, app_set, user_set, graph_dict, i, sim_folder)
        i += 1

    pass

def main():
    random.seed(42)

    # MANUAL GENERATION OF GRAPH: config_manual = "config_manual.yaml"
    config_random = "config_random.yaml"
    config = load_config(config_random)

    generated_events = EventSet()

    # RANDOM GENERATION OF GRAPH
    generated_infrastructure = generate_infrastructure(config, generated_events)
    actual_graph = generated_infrastructure.get_main_graph() 

    generated_apps = generate_random_apps(config, generated_events)
    print(f"Apps: {generated_apps}")

    generated_users = generate_random_users(config, generated_apps, generated_infrastructure, generated_events)
    print(f"\nUsers: {generated_users}")

    init_new_object(config, generated_events)

    print("\nEvents:", generated_events)

    # SOLVE PROBLEM
    if generated_apps and generated_users and generated_infrastructure:
        optimal_placement, total_latency = solve_application_placement(generated_infrastructure, generated_apps, generated_users)
        if optimal_placement:
            print("Application Placement:", optimal_placement)
            print("Total Latency:", total_latency)
            print("\nUpdated Node Information with Application Placement:")
            for node, feat in actual_graph.nodes(data=True):
                print(f"Node {node}: RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, Running Apps={[generated_apps.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}")
        else:
            print("No feasible solution found for application placement.")
    
    # WORKING ON ITERATIONS
    print("\n---- EVENTS ----")
    generate_scenario(generated_events, config, generated_apps, generated_users, generated_infrastructure)


if __name__ == "__main__":
    main()
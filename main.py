# BORRAR: Here I will be running all the main code and calling the classeskept in other files
# BORRAR: from src.experimentSetup import experimentSetup

import yaml
import random
import uuid
import networkx as nx
from pulp import *
import pickle

from src import EventSet, generate_events, ApplicationSet, generate_random_apps, UserSet, generate_random_users
from utils import get_random_from_range

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def _generate_random_graph(config):
    """Internal function to handle the 'random' generation mode."""
    setup = config.get('setup', {})
    model_params = config.get('model_params', {})
    
    model_name = setup.get('graph_model', 'erdos_renyi') # set to default if it's empty
    num_nodes = setup.get('num_nodes', 10)
    
    print(f"  [Random Mode] Generating {model_name} graph with {num_nodes} nodes...")
    
    # 1. Generate Topology
    if model_name == 'erdos_renyi':
        p = model_params.get('p', 0.1)
        graph = nx.erdos_renyi_graph(num_nodes, p)
    elif model_name == 'barabasi_albert':
        m = model_params.get('m', 2)
        if m >= num_nodes: m = 1
        graph = nx.barabasi_albert_graph(num_nodes, m)
    elif model_name == 'watts_strogatz':
        k = model_params.get('k', 4)
        p = model_params.get('p_rewire', 0.1)
        if k >= num_nodes: k = num_nodes - 1
        graph = nx.watts_strogatz_graph(num_nodes, k, p)
    elif model_name == 'balanced_tree':
        r = model_params.get('r', 2) 
        h = model_params.get('h', 3)
        graph = nx.balanced_tree(r, h)
    else:
        print(f"Graph model '{model_name}' not recognized.")
        return None

    # 2. Assign Random Attributes
    for node in graph.nodes():
        graph.nodes[node]['ram'] = get_random_from_range(config, 'node', 'ram')

    # 3. Assign Random Edge Delays
    for u, v in graph.edges():
        # BORRAR: graph.edges[u, v]['delay'] = round(random.uniform(0.1, 5.0), 2)
        graph.edges[u, v]['delay'] = get_random_from_range(config, 'edge', 'delay')
    return graph

# BORRAR: por ahora lo dejo estar
def _generate_manual_graph(config):
    """Internal function to handle the 'manual' generation mode."""
    print("  [Manual Mode] Building graph from defined topology...")
    graph = nx.Graph()
    
    topology = config.get('topology', {})
    
    # 1. Add Nodes with specific attributes
    for node_data in topology.get('nodes', []):
        # We pop 'id' so it isn't stored as an attribute inside the node dict itself
        # but used as the key in the graph
        data_copy = node_data.copy()
        node_id = data_copy.pop('id') 
        graph.add_node(node_id, **data_copy)
        
    # 2. Add Edges with specific attributes
    for edge_data in topology.get('edges', []):
        data_copy = edge_data.copy()
        u = data_copy.pop('source')
        v = data_copy.pop('target')
        graph.add_edge(u, v, **data_copy)
        
    return graph

def generate_infrastructure(config):
    """
    Main entry point. Switches between manual and random generation
    based on the 'mode' setting in YAML.
    """
    setup = config.get('setup', {})
    mode = setup.get('mode', 'random')
    
    if mode == 'manual':
        graph = _generate_manual_graph(config)
    else:
        graph = _generate_random_graph(config)

    # --- Common Post-Processing ---
    # We calculate centrality for BOTH modes (unless you want to manually define it too)
    if graph and graph.number_of_nodes() > 0:
        try:
            betweenness_centrality = nx.betweenness_centrality(graph)
            for node, centrality in betweenness_centrality.items():
                graph.nodes[node]['betweenness_centrality'] = round(centrality, 4)
        except Exception as e:
            print(f"Could not calculate centrality: {e}")

    return graph

def solve_application_placement(graph, application_set, user_set):
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

# REVISAR: CARLOS no sé si esta es la forma más óptima de hacerlo
def update_system_state(events_list, update_set):
    # Apply action to the set user_set or app_set
    event = events_list.get_first_event()
    eval(f"update_set.{event['action']}('{event['object_id']}')")

    if events_list.get_first_event()['action'].startswith('remove'):
        events_list.remove_event(events_list.get_first_event()['id'])
        print(update_set)
        print("Update event list después update:", events_list)
        print(" ")

    elif events_list.get_first_event()['action'].startswith('move'):
        # user_set.move_user(event[1]['id'])) # por graph
        # Hay que actualizar el nodo al que está conectado el usuario
        # y también hay que asignar un nuevo tiempo: random time + global_time
        pass

def scenario1(events_list, app_set, user_set):
    global_time = 0
    max_iterations = 1

    while events_list.events and max_iterations < 10: # and global_time < 300
        # 1 Sort the events by time
        # 2 Get first event
        # 3 Update everything (user_set/app_set and events_list)
        # 3.2 Update global_time!!
        # 4 Save new scenario and solutions
        print("Paso ", max_iterations)
        events_list.sort_by_time()
        # REVISAR: aquí tengo que coger el mínimo, no hacer sort
        set_for_update = eval(events_list.get_first_event()['type_object'] + '_set')
        update_system_state(events_list, set_for_update)

        max_iterations += 1

    pass

def main():
    random.seed(42)

    # MANUAL GENERATION OF GRAPH: config_manual = "config_manual.yaml"

    config_random = "config_random.yaml"
    config = load_config(config_random)

    # RANDOM GENERATION OF GRAPH
    generated_infrastructure = generate_infrastructure(config)
    print(f"Nodes: {generated_infrastructure.number_of_nodes()}")
    print(f"Edges: {generated_infrastructure.number_of_edges()}")

    generated_apps = generate_random_apps(config)
    print(f"Apps: {generated_apps}")

    generated_users = generate_random_users(config, generated_apps, generated_infrastructure)
    print(f"Users: {generated_users}")

    # SOLVE PROBLEM
    if generated_apps and generated_users and generated_infrastructure:
        optimal_placement, total_latency = solve_application_placement(generated_infrastructure, generated_apps, generated_users)

        if optimal_placement:
            print("Application Placement:", optimal_placement)
            print("Total Latency:", total_latency)
            print("\nUpdated Node Information with Application Placement:")
            for node in generated_infrastructure.nodes(data=True):
                print(f"Node {node[0]}: RAM Total={node[1].get('ram')}, RAM Used={node[1].get('ram_used')}, Running Apps={[generated_apps.get_application(app_id)['name'] for app_id in node[1].get('running_applications', [])]}")
            # return optimal_placement
        else:
            print("No feasible solution found for application placement.")

    all_results = []

    current_result = {
        "infrastructure": generated_infrastructure,
        "apps": generated_apps,
        "users": generated_users,
        "iteration_id": 0,
        "event": "START",
        "placement": optimal_placement,
        "total_latency": total_latency
    }
    
    all_results.append(current_result)
    


    # WORKING ON ITERATIONS
    print("\n---- EVENTS ----")
    print("Users son", generated_users)
    
    generated_events = EventSet()
    generated_events = generate_events(generated_users, 'user', generated_events)
    # REVISAR: Por ahora no añado las apps aún
    # generated_events = generate_events(generated_apps, 'app', generated_events)
    print("Events son:", generated_events)

    print("Elemento eliminado: ", list(generated_users.get_all_users().keys())[0])
    # generated_users.remove_user(list(generated_users.get_all_users().keys())[0])  # Remove first user for testing

    scenario1(generated_events, generated_apps, generated_users)

    
    with open('simulation_results.pkl', 'wb') as f:  # 'wb' means Write Binary
        pickle.dump(all_results, f)

    print("Objects saved to simulation_results.pkl")


if __name__ == "__main__":
    main()

            

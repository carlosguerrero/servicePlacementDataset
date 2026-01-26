import yaml
import random
import uuid
import networkx as nx
from pulp import *
import pickle
import copy

from src import EventSet, generate_events, init_new_object, ApplicationSet, generate_random_apps, UserSet, generate_random_users, InfrastructureGraph, _generate_random_graph, _generate_manual_graph, generate_infrastructure
from src.utils.auxiliar_functions import get_random_from_range

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

# BORRAR
# def _generate_random_graph(config):
#     """Internal function to handle the 'random' generation mode."""
#     setup = config.get('setup', {})
#     model_params = config.get('model_params', {})
    
#     model_name = setup.get('graph_model', 'erdos_renyi') # set to default if it's empty
#     num_nodes = setup.get('num_nodes', 10)
    
#     print(f"  [Random Mode] Generating {model_name} graph with {num_nodes} nodes...")
    
#     # 1. Generate Topology
#     if model_name == 'erdos_renyi':
#         p = model_params.get('p', 0.1)
#         graph = nx.erdos_renyi_graph(num_nodes, p)
#     elif model_name == 'barabasi_albert':
#         m = model_params.get('m', 2)
#         if m >= num_nodes: m = 1
#         graph = nx.barabasi_albert_graph(num_nodes, m)
#     elif model_name == 'watts_strogatz':
#         k = model_params.get('k', 4)
#         p = model_params.get('p_rewire', 0.1)
#         if k >= num_nodes: k = num_nodes - 1
#         graph = nx.watts_strogatz_graph(num_nodes, k, p)
#     elif model_name == 'balanced_tree':
#         r = model_params.get('r', 2) 
#         h = model_params.get('h', 3)
#         graph = nx.balanced_tree(r, h)
#     else:
#         print(f"Graph model '{model_name}' not recognized.")
#         return None

#     # 2. Assign Random Ram
#     for node in graph.nodes():
#         graph.nodes[node]['ram'] = get_random_from_range(config, 'node', 'ram')
#         graph.nodes[node]['enable'] = True

#     # 3. Assign Random Edge Delays
#     for u, v in graph.edges():
#         graph.edges[u, v]['delay'] = get_random_from_range(config, 'edge', 'delay')

#     return graph

# BORRAR: por ahora lo dejo estar
# def _generate_manual_graph(config):
#     """Internal function to handle the 'manual' generation mode."""
#     print("  [Manual Mode] Building graph from defined topology...")
#     graph = nx.Graph()
    
#     topology = config.get('topology', {})
    
#     # 1. Add Nodes with specific attributes
#     for node_data in topology.get('nodes', []):
#         # We pop 'id' so it isn't stored as an attribute inside the node dict itself
#         # but used as the key in the graph
#         data_copy = node_data.copy()
#         node_id = data_copy.pop('id') 
#         graph.add_node(node_id, **data_copy)
        
#     # 2. Add Edges with specific attributes
#     for edge_data in topology.get('edges', []):
#         data_copy = edge_data.copy()
#         u = data_copy.pop('source')
#         v = data_copy.pop('target')
#         graph.add_edge(u, v, **data_copy)
        
#     return graph

# def generate_infrastructure(config):
#     """
#     Main entry point. Switches between manual and random generation
#     based on the 'mode' setting in YAML.
#     """
#     setup = config.get('setup', {})
#     mode = setup.get('mode', 'random')
    
#     if mode == 'manual':
#         graph = _generate_manual_graph(config)
#     else:
#         graph = _generate_random_graph(config)

#     # --- Common Post-Processing ---
#     # We calculate centrality for BOTH modes (unless you want to manually define it too)
#     if graph and graph.number_of_nodes() > 0:
#         try:
#             betweenness_centrality = nx.betweenness_centrality(graph)
#             for node, centrality in betweenness_centrality.items():
#                 graph.nodes[node]['betweenness_centrality'] = round(centrality, 4)
#         except Exception as e:
#             print(f"Could not calculate centrality: {e}")

#     return graph

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

# BORRAR
# def disable_node(graph, node_id):
#     if node_id in graph.nodes:
#         graph.nodes[node_id]['enable'] = False
#         print(f"Node {node_id} has been disabled.")

#         update_shortest_paths(graph)
#     else:
#         print(f"Node {node_id} not found in the graph.")

# def revive_node(graph, node_id):
#     if node_id in graph.nodes:
#         graph.nodes[node_id]['enable'] = True
#         print(f"Node {node_id} has been revived.")

#         update_shortest_paths(graph)
#     else:
#         print(f"Node {node_id} not found in the graph.")

# def update_shortest_paths(graph):
#     """
#     Recalculates shortest paths based on currently ACTIVE nodes 
#     and stores them in the graph's metadata.
#     """
#     active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]

#     if not active_nodes:
#         graph.graph['shortest_paths'] = {}
#         return

#     active_subgraph = graph.subgraph(active_nodes)

#     try:
#         # We store the dictionary of shortest paths in graph.graph
#         graph.graph['shortest_paths'] = dict(nx.all_pairs_dijkstra_path_length(active_subgraph, weight='delay'))
#         print("GRAPH: shortest paths updated") 
#     except Exception as e:
#         print(f"  [Error] Path calculation failed: {e}")
#         graph.graph['shortest_paths'] = {}

def solve_application_placement(graph, application_set, user_set):
    PENALTY_DELAY = 1_000_000 

    # --- NEW: Lazy Load / Cache Access ---
    # If the cache doesn't exist yet, calculate it now.
    if 'shortest_paths' not in graph.graph:
        print("  [Info] Initializing shortest paths cache...")
        update_shortest_paths(graph)
    
    # Retrieve pre-calculated paths
    all_pairs_shortest_paths = graph.graph['shortest_paths']
    # -------------------------------------

    applications = application_set.get_all_apps()
    users = user_set.get_all_users()
    
    # Filter active nodes for constraints
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
        for app_id, app_data in applications.items():
            for node in active_nodes:
                if value(x_an[app_id, node]) == 1:
                    placement[app_data['name']] = node
                    break
        return placement, current_objective
    else:
        return None, PENALTY_DELAY

def update_system_state(events_list, config, app_set, user_set, infrastructure):
    first_event = events_list.get_first_event()
    set_map = {
        'user': user_set,
        'app': app_set,
        'infrastructure': infrastructure 
    }

    events_list.global_time = first_event['time']
    
    # Identify which set we need to update based on 'type_object': user, app, infrastructure
    target_object = set_map.get(first_event['type_object'])
    if not target_object:
        raise ValueError(f"Unknown object type: {first_event['type_object']}")

    events_list.update_event_params(first_event['id'], config, app_set, user_set, infrastructure)
    params = first_event['action_params']
    if params == 'None':
        params = None
    
    # Ensure event_set is always included in params for actions that need it
    if params is None:
        params = {}
    if isinstance(params, dict):
        params['event_set'] = events_list

    print("Processing event:", first_event['action'])
    print("Time event:", first_event['time'])

    action_method = getattr(target_object, first_event['action'])
    action_method(first_event['object_id'], params)

    events_list.update_event(first_event['id'], config)
    
def generate_scenario(events_list, config, app_set, user_set, infrastructure):
    max_iterations = 1

    while events_list.events and max_iterations < 20: # and global_time < 300
        print("ITERATION", max_iterations)
        # 2 Get first event
        # 3 Update everything (user_set/app_set and events_list)
        # 3.2 Update global_time!!
        # 4 Save new scenario and solutions
        update_system_state(events_list, config, app_set, user_set, infrastructure)

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

    generated_events = EventSet()

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
            for node, feat in generated_infrastructure.nodes(data=True):
                print(f"Node {node}: RAM Total={feat.get('ram')}, RAM Used={feat.get('ram_used')}, Running Apps={[generated_apps.get_application(app_id)['name'] for app_id in feat.get('running_applications', [])]}")
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

    generate_scenario(generated_events, config, generated_apps, generated_users, generated_infrastructure)

    
    with open('simulation_results.pkl', 'wb') as f:  # 'wb' means Write Binary
        pickle.dump(all_results, f)

    print("Objects saved to simulation_results.pkl")


if __name__ == "__main__":
    main()
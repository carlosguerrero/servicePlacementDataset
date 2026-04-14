import random
import copy
import os
from datetime import datetime

def get_random_from_range(config, category, key, distribution=None):
    """Helper to get a random float between min and max defined in YAML.
    with the probability distribution function as we choose.
    """
    r = config['attributes'][category][key]
    dist_func = distribution if distribution else random.uniform
    return round(dist_func(r[0], r[1]), 2)

def selectRandomAction(type_object, probabilities):
    if type_object == 'user':
        actions = ["remove_user", "move_user"]
        return random.choices(actions, weights=probabilities, k=1)[0]
        # necesito asignarle una acción aleatoria de la lista:
        # remove_user o move_user
    elif type_object == 'app':
        # REVISAR
        actions = ["remove_app", "add_app"]
        return random.choices(actions, weights=probabilities, k=1)[0]
    else:
        return "No type_object recognized"

def selectRandomGraphNodeByCentrality(graph_dict, centrality, sim_set, node=None):  
    """
    Selects a random node from the graph based on its betweenness centrality.

    Args:
        graph (networkx.Graph): The input graph.
        centrality (float): The centrality threshold for selection.

    Returns:
        str: The ID of the selected node.
    """
    actual_graph = graph_dict.get_main_graph() 
    nodes_dict = dict(actual_graph.nodes(data=True))
    nodes_copy = copy.deepcopy(nodes_dict)

    if node in nodes_copy:
        del nodes_copy[node]

    selected_nodes = [node for node, data in nodes_copy.items() if data['betweenness_centrality'] <= centrality]

    if selected_nodes:
        rng = sim_set.rng_graph
        selected_node = rng.choice(selected_nodes)
        return int(selected_node)
    return None

# BORRAR
def selectAdjacentNodeWhenMoving2(graph_dict, node_id, centrality, sim_set, active=True):  
    """
    This function selects a node from the nodes that have an edge
    attached to the given "node" as argument
    The nodes that have a higher betweenness centrality than "centrality"
    are not chosen (we want the periphery nodes)
    The node needs to be chosen randomly but we have weights favoring the 
    betweenness centrality (the lowest betweenness centrality gets the highest weight)
    """
    rng = sim_set.rng_graph

    actual_graph = graph_dict.get_main_graph() 

    adjacent_nodes = actual_graph.neighbors(node_id)

    adjacent_nodes_info = {
        n: {
            'betweenness_centrality': actual_graph.nodes[n].get('betweenness_centrality', 0),
            'enable': actual_graph.nodes[n].get('enable', True)
        }
        for n in adjacent_nodes
    }

    adjacent_nodes_info_filtered = {
        n: info 
        for n, info in adjacent_nodes_info.items() 
        if info['betweenness_centrality'] <= centrality and info['enable']
    }

  
    if not adjacent_nodes_info_filtered:
        adjacent_nodes_info_filtered = list(actual_graph.neighbors(node_id))
        selection = rng.choice(adjacent_nodes_info_filtered)
        return int(selection)

    
    # From the filtered nodes,
    # We want to choose the node randomly but with weights favoring the lowest betweenness centrality
    nodes = list(adjacent_nodes_info_filtered.keys())
    centralities = [info['betweenness_centrality'] for info in adjacent_nodes_info_filtered.values()]
    epsilon = 0.0001
    max_c = max(centralities) + epsilon
    weights = [max_c - c for c in centralities]
    probabilities = [w / sum(weights) for w in weights]
    selection = rng.choice(nodes, p=probabilities, size=1)

    return int(selection[0])


def selectAdjacentNodeWhenMoving(graph_dict, node_id, centrality, sim_set, active=True):  
    """
    This function selects a node starting from the direct neighbors of the given "node_id".
    If no nodes meet the centrality and 'enable' condition, it expands the search to 
    neighbors of neighbors (distance 2), then distance 3, etc., layer by layer.
    
    The node needs to be chosen randomly but we have weights favoring the 
    betweenness centrality (the lowest betweenness centrality gets the highest weight).
    """
    rng = sim_set.rng_graph
    actual_graph = graph_dict.get_main_graph() 

    visited = {node_id}
    
    current_layer = list(actual_graph.neighbors(node_id))
    adjacent_nodes_info_filtered = {}

    while current_layer:
        for n in current_layer:
            visited.add(n) 
            
            bc = actual_graph.nodes[n].get('betweenness_centrality', 0)
            enabled = actual_graph.nodes[n].get('enable', True)
            
            if enabled and bc <= centrality:
                adjacent_nodes_info_filtered[n] = {
                    'betweenness_centrality': bc,
                    'enable': enabled
                }
        
        if adjacent_nodes_info_filtered:
            break
            
        next_layer = []
        for n in current_layer:
            for neighbor in actual_graph.neighbors(n):
                if neighbor not in visited:
                    next_layer.append(neighbor)
                    visited.add(neighbor) 
                    
        current_layer = next_layer

    if not adjacent_nodes_info_filtered:
        direct_neighbors = [n for n in actual_graph.neighbors(node_id) if actual_graph.nodes[n].get('enable', True)]
        
        if direct_neighbors:
            selection = rng.choice(direct_neighbors)
            return int(selection)
        else:
            return node_id
    
    nodes = list(adjacent_nodes_info_filtered.keys())
    centralities = [info['betweenness_centrality'] for info in adjacent_nodes_info_filtered.values()]
    
    epsilon = 0.0001
    max_c = max(centralities) + epsilon
    weights = [max_c - c for c in centralities]
    probabilities = [w / sum(weights) for w in weights]
    
    selection = rng.choice(nodes, p=probabilities, size=1)

    return int(selection[0])
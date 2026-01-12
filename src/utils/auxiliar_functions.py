import random
import copy

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

def selectRandomGraphNodeByCentrality(graph, centrality, node=None):  
    """
    Selects a random node from the graph based on its betweenness centrality.

    Args:
        graph (networkx.Graph): The input graph.
        centrality (float): The centrality threshold for selection.

    Returns:
        str: The ID of the selected node.
    """
    nodes_dict = dict(graph.nodes(data=True))
    nodes_copy = copy.deepcopy(nodes_dict)
    if node in nodes_copy:
        del nodes_copy[node]

    # BORRAR: selected_nodes = [node for node, data in graph.nodes(data=True) if data['betweenness_centrality'] <= centrality]
    selected_nodes = [node for node, data in nodes_copy.items() if data['betweenness_centrality'] <= centrality]
    if selected_nodes:
        return random.choice(selected_nodes)
    return None

def selectAdjacentNodeWhenMoving(graph, node_id, centrality, active=True):  
    """
    This function selects a node from the nodes that have an edge
    attached to the given "node" as argument
    The nodes that have a higher betweenness centrality than "centrality"
    are not chosen (we want the periphery nodes)
    The node needs to be chosen randomly but we have weights favoring the 
    betweenness centrality (the lowest betweenness centrality gets the highest weight)
    """
    adjacent_nodes = graph.neighbors(node_id)

    adjacent_nodes_info = {
        n: {
            'betweenness_centrality': graph.nodes[n].get('betweenness_centrality', 0),
            'enable': graph.nodes[n].get('enable', True)
        }
        for n in adjacent_nodes
    }

    adjacent_nodes_info_filtered = {
        n: info 
        for n, info in adjacent_nodes_info.items() 
        if info['betweenness_centrality'] <= centrality and info['enable']
    }

  
    if not adjacent_nodes_info_filtered:
        return None
    
    # From the filtered nodes,
    # We want to choose the node randomly but with weights favoring the lowest betweenness centrality
    nodes = list(adjacent_nodes_info_filtered.keys())
    centralities = [info['betweenness_centrality'] for info in adjacent_nodes_info_filtered.values()]

    epsilon = 0.0001
    max_c = max(centralities) + epsilon
    weights = [max_c - c for c in centralities]
    selection = random.choices(nodes, weights=weights, k=1)

    return selection[0]
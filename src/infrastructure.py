import networkx as nx
import random
from .eventSet import generate_events

class InfrastructureGraph(nx.Graph):
    def __init__(self, incoming_graph_data=None, actions=None, **attr):
        # Initialize the standard NetworkX graph
        super().__init__(incoming_graph_data, **attr)

        self.actions = actions if actions is not None else {}
        
        if 'shortest_paths' not in self.graph:
            self.update_shortest_paths()

    def update_shortest_paths(self):
        """Recalculates shortest paths for active nodes and stores in metadata."""
        # Filter active nodes directly from self
        active_nodes = [n for n, attrs in self.nodes(data=True) if attrs.get('enable', True)]

        if not active_nodes:
            self.graph['shortest_paths'] = {}
            return

        # Create a subgraph view of only active nodes
        active_subgraph = self.subgraph(active_nodes)

        try:
            self.graph['shortest_paths'] = dict(nx.all_pairs_dijkstra_path_length(active_subgraph, weight='delay'))
            # print("  [Graph] Shortest paths cache updated.") 
        except Exception as e:
            print(f"  [Error] Path calculation failed: {e}")
            self.graph['shortest_paths'] = {}

    def disable_random_node(self, node_id, params=None):
        """
        Selects a random active node to disable, biased towards peripheral nodes
        (lower betweenness centrality = higher chance of being disabled).
        """
        active_candidates = [
            (n, attrs) for n, attrs in self.nodes(data=True) 
            if attrs.get('enable', True)
        ]

        if not active_candidates:
            print("  [Warning] No active nodes available to disable.")
            return

        epsilon = 1e-6
        weights = []
        node_ids = []

        for node_id, attrs in active_candidates:
            centrality = attrs.get('betweenness_centrality', 0)
            
            w = 1.0 / (centrality + epsilon)
            
            weights.append(w)
            node_ids.append(node_id)

        selected_node = random.choices(node_ids, weights=weights, k=1)[0]
        print(f"  [Event] Randomly selected node {selected_node} (Centrality: {self.nodes[selected_node].get('betweenness_centrality')})")

        self.disable_node(selected_node)

        # We need to add "revive_node" to the event list for this selected_node
        event_set = params.get('event_set')
        distribution_to_enable_node = eval(params.get('distribution_to_enable_node'))

        eventAttributes = event_set.newEventItem(
            object_id=selected_node,
            type_object='graph',
            time=distribution_to_enable_node + event_set.global_time,
            action='revive_node',
            action_params=None
        )
        event_set.add_event(eventAttributes)


    def disable_node(self, node_id, params=None):
        """Disables a node and automatically updates paths."""
        if node_id in self.nodes:
            self.nodes[node_id]['enable'] = False
            print(f"Node {node_id} has been disabled.")
            self.update_shortest_paths()
        else:
            print(f"Node {node_id} not found in the graph.")

    def revive_node(self, node_id, params=None):
        """Revives a node and automatically updates paths."""
        if node_id in self.nodes:
            self.nodes[node_id]['enable'] = True
            print(f"Node {node_id} has been revived.")
            self.update_shortest_paths()
        else:
            print(f"Node {node_id} not found in the graph.")

def _generate_random_graph(config, event_set):
    """Internal function to handle the 'random' generation mode."""
    setup = config.get('setup', {})
    model_params = config.get('model_params', {})
    
    model_name = setup.get('graph_model', 'erdos_renyi') # set to default if it's empty
    num_nodes = setup.get('num_nodes', 10)
    
    print(f"  [Random Mode] Generating {model_name} graph with {num_nodes} nodes...")

    if model_name == 'erdos_renyi':
        p = model_params.get('p', 0.1)
        temp_graph = nx.erdos_renyi_graph(num_nodes, p)
    elif model_name == 'barabasi_albert':
        m = model_params.get('m', 2)
        if m >= num_nodes: m = 1
        temp_graph = nx.barabasi_albert_graph(num_nodes, m)
    elif model_name == 'watts_strogatz':
        k = model_params.get('k', 4)
        p = model_params.get('p_rewire', 0.1)
        if k >= num_nodes: k = num_nodes - 1
        temp_graph = nx.watts_strogatz_graph(num_nodes, k, p)
    elif model_name == 'balanced_tree':
        r = model_params.get('r', 2) 
        h = model_params.get('h', 3)
        temp_graph = nx.balanced_tree(r, h)
    else:
        print(f"Graph model '{model_name}' not recognized.")
        return None

    actions_list = config['attributes']['infrastructure'].get('actions', {})
    
    graph = InfrastructureGraph(temp_graph, actions=actions_list)

    for node in graph.nodes():
        graph.nodes[node]['ram'] = eval(config['attributes']['node']['ram'])
        graph.nodes[node]['enable'] = True

    for u, v in graph.edges():
        graph.edges[u, v]['delay'] = eval(config['attributes']['edge']['delay'])

    graph.update_shortest_paths()

    generate_events(graph, 'graph', event_set)
    
    return graph

# BORRAR: por ahora lo dejo estar
def _generate_manual_graph(config):
    print("  [Manual Mode] Building graph from defined topology...")
    graph = InfrastructureGraph()
    
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

def generate_infrastructure(config, event_set):
    """
    Main entry point. Switches between manual and random generation
    based on the 'mode' setting in YAML.
    """
    setup = config.get('setup', {})
    mode = setup.get('mode', 'random')
    
    if mode == 'manual':
        graph = _generate_manual_graph(config)
    else:
        graph = _generate_random_graph(config, event_set)

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
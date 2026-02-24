import networkx as nx
import random
from .eventSet import generate_events

class InfrastructureSet: 
    def __init__(self):
        # Format: {'000': {'id': '000', 'graph': nx_graph, 'shortest_paths': dict, 'actions': dict}}
        self.infrastructures = {} 

    def get_main_graph(self):
        """Helper to get the actual NetworkX object (useful for the Solver in main.py)"""
        return self.infrastructures.get('000', {}).get('graph')

    def init_infrastructure(self, nx_graph, actions=None):
        """
        Wraps the NetworkX graph into the standard dictionary format 
        and adds it to the set.
        """
        obj_id = "000"  
        actions = actions if actions is not None else {}
        
        shortest_paths = self._calculate_shortest_paths(nx_graph)

        # Create the dictionary item
        infra_item = {
            'id': obj_id,
            'graph': nx_graph,
            'shortest_paths': shortest_paths,
            'actions': actions
        }

        self.infrastructures[obj_id] = infra_item
        return infra_item

    def _calculate_shortest_paths(self, graph):
        """Internal helper to calculate paths on a specific graph instance."""
        # Filter active nodes
        active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]

        if not active_nodes:
            return {}

        active_subgraph = graph.subgraph(active_nodes)
        try:
            return dict(nx.all_pairs_dijkstra_path_length(active_subgraph, weight='delay'))
        except Exception as e:
            print(f"  [Error] Path calculation failed: {e}")
            return {}

    def update_shortest_paths(self, infra_id="000"):
        """Recalculates shortest paths for the specific infrastructure item."""
        item = self.infrastructures.get(infra_id)
        if item:
            item['shortest_paths'] = self._calculate_shortest_paths(item['graph'])

    def get_active_nodes(self, infra_id="000"):
        """
        Returns a list of active node IDs (nodes with 'enable' == True).
        If infra_id is not found or has no graph, returns an empty list.
        """
        item = self.infrastructures.get(infra_id)
        if not item:
            return []
        
        graph = item['graph']
        active_nodes = [
            n for n, attrs in graph.nodes(data=True) 
            if attrs.get('enable', True)
        ]
        return active_nodes

    def get_active_edges(self, infra_id="000"):
        """
        Returns a list of active edge tuples (edges with 'enable' == True).
        If infra_id is not found or has no graph, returns an empty list.
        """
        item = self.infrastructures.get(infra_id)
        if not item:
            return []
        
        graph = item['graph']
        active_edges = [
            (u, v) for u, v, attrs in graph.edges(data=True)
            if attrs.get('enable', True)
        ]
        return active_edges

    def disable_random_node(self, infra_id, params=None):
        """Selects and disables a random node in the specified graph."""
        item = self.infrastructures.get(infra_id)
        if not item: return

        graph = item['graph']
        
        active_candidates = [
            (n, attrs) for n, attrs in graph.nodes(data=True) 
            if attrs.get('enable', True)
        ]

        if not active_candidates:
            print("  [Warning] No active nodes available to disable.")
            return

        epsilon = 1e-6
        weights = [1.0 / (attrs.get('betweenness_centrality', 0) + epsilon) for _, attrs in active_candidates]
        node_ids = [n for n, _ in active_candidates]

        selected_node = random.choices(node_ids, weights=weights, k=1)[0]

        # Call disable_node passing the infrastructure ID
        self.disable_node(infra_id, {'node_id': selected_node})

        # Schedule Revival
        event_set = params.get('event_set')
        distribution_to_enable_node = eval(params.get('distribution_to_enable_node', '10'))

        eventAttributes = event_set.newEventItem(
            object_id=infra_id, # The event targets the Graph Object '000'
            type_object='graph',
            time=distribution_to_enable_node + event_set.global_time,
            action='revive_node',
            action_params={'node_id': selected_node, 'event_set': None, 'associated_event_id': None}
        )
        associated_event_id = event_set.add_event(eventAttributes)
        event_set.events[associated_event_id]['action_params']['associated_event_id'] = associated_event_id

        message = f"Node {selected_node} has been disabled. Scheduled revival in {distribution_to_enable_node} time units."
        return message


    def disable_node(self, infra_id, params=None):
        """Disables a node in the graph and updates paths."""
        if params is None: params = {}
        node_id = params.get('node_id') or infra_id # Handle if passed directly or in params
        
        # We assume operations target the main graph '000' if infra_id is the object_id
        item = self.infrastructures.get(infra_id) 
        if item and node_id in item['graph'].nodes:
            item['graph'].nodes[node_id]['enable'] = False
            self.update_shortest_paths(infra_id)
        else:
            print(f"Node {node_id} not found in graph {infra_id}.")

    def revive_node(self, infra_id, params=None):
        """Revives a node in the graph and updates paths."""
        if params is None: params = {}
        event_set = params.get('event_set')
        node_id = params.get('node_id')
        associated_event_id = params.get('associated_event_id') # The event_id where this revival is "activated"

        item = self.infrastructures.get(infra_id)
        if item and node_id in item['graph'].nodes:
            item['graph'].nodes[node_id]['enable'] = True
            self.update_shortest_paths(infra_id)
        else:
            print(f"Node {node_id} not found in graph {infra_id}.")
        
        event_set.remove_event(associated_event_id)

        message = f"Node {node_id} has been revived."
        return message
    
    def disable_random_edge(self, infra_id, params=None):
        """Selects and disables a random edge in the specified graph."""
        item = self.infrastructures.get(infra_id)
        if not item:
            return

        graph = item['graph']
        # Only consider enabled edges
        active_edges = [
            (u, v) for u, v, attrs in graph.edges(data=True)
            if attrs.get('enable', True)
        ]
        if not active_edges:
            print("  [Warning] No active edges available to disable.")
            return

        selected_edge = random.choice(active_edges)
        print(f"  [Event] Randomly selected edge {selected_edge}")

        self.disable_edge(infra_id, {'edge': selected_edge})

        # Schedule Revival
        event_set = params.get('event_set')
        distribution_to_enable_edge = eval(params.get('distribution_to_enable_edge', '10'))

        eventAttributes = event_set.newEventItem(
            object_id=infra_id,
            type_object='graph',
            time=distribution_to_enable_edge + event_set.global_time,
            action='revive_edge',
            action_params={'edge': selected_edge, 'event_set': None, 'associated_event_id': None}
        )
        associated_event_id = event_set.add_event(eventAttributes)
        event_set.events[associated_event_id]['action_params']['associated_event_id'] = associated_event_id

        message = f"Edge {selected_edge} has been disabled. Scheduled revival in {distribution_to_enable_edge} time units."
        return message

    def disable_edge(self, infra_id, params=None):
        """Disables an edge in the graph and updates paths."""
        if params is None:
            params = {}
        edge = params.get('edge')
        item = self.infrastructures.get(infra_id)
        if item and edge and item['graph'].has_edge(*edge):
            item['graph'].edges[edge]['enable'] = False
            self.update_shortest_paths(infra_id)
        else:
            print(f"Edge {edge} not found in graph {infra_id}.")

    def revive_edge(self, infra_id, params=None):
        """Revives an edge in the graph and updates paths."""
        if params is None:
            params = {}
        event_set = params.get('event_set')
        edge = params.get('edge')
        associated_event_id = params.get('associated_event_id')
        item = self.infrastructures.get(infra_id)
        if item and edge and item['graph'].has_edge(*edge):
            item['graph'].edges[edge]['enable'] = True
            self.update_shortest_paths(infra_id)
        else:
            print(f"Edge {edge} not found in graph {infra_id}.")
        if event_set and associated_event_id:
            event_set.remove_event(associated_event_id)
        message = f"Edge {edge} has been revived."
        return message

def _generate_random_graph(config, event_set):
    """Internal function to handle the 'random' generation mode."""
    setup = config.get('setup', {})
    model_params = config.get('model_params', {})
    
    model_name = setup.get('graph_model', 'erdos_renyi')
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

    # Apply Attributes
    for node in temp_graph.nodes():
        temp_graph.nodes[node]['ram'] = eval(config['attributes']['graph']['node']['ram'])
        temp_graph.nodes[node]['enable'] = True

    for u, v in temp_graph.edges():
        temp_graph.edges[u, v]['delay'] = eval(config['attributes']['graph']['edge']['delay'])

    graph_set = InfrastructureSet()
    actions_list = config['attributes']['graph'].get('actions', {})
    
    # This creates the dictionary item {'000': {graph:..., actions:...}}
    graph_item = graph_set.init_infrastructure(temp_graph, actions=actions_list)

    generate_events(graph_item, 'graph', event_set)
    
    return graph_set

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
        # graph = _generate_manual_graph(config)
        pass
    else:
        graph_dict = _generate_random_graph(config, event_set)
        graph = graph_dict.get_main_graph()

    if graph and graph.number_of_nodes() > 0:
        try:
            betweenness_centrality = nx.betweenness_centrality(graph)
            for node, centrality in betweenness_centrality.items():
                graph.nodes[node]['betweenness_centrality'] = round(centrality, 4)
        except Exception as e:
            print(f"Could not calculate centrality: {e}")
    
    return graph_dict
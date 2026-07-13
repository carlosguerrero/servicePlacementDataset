import networkx as nx
import numpy as np
import logging
from .eventSet import generate_events
from .constants import DEFAULT_INFRA_ID
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Note: I just added the DESCOMENTAR line to indicate where the event generation for the graph would be triggered

class InfrastructureSet: 
    def __init__(self) -> None:
        # Format: {'000': {'id': '000', 'graph': nx_graph, 'shortest_paths': dict, 'actions': dict}}
        self.infrastructures: Dict[str, Dict[str, Any]] = {} 

    def get_main_graph(self) -> Optional[nx.Graph]:
        """Helper to get the actual NetworkX object (useful for the Solver in main.py)"""
        return self.infrastructures.get(DEFAULT_INFRA_ID, {}).get('graph')

    def init_infrastructure(self, nx_graph: nx.Graph, actions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Wraps the NetworkX graph into the standard dictionary format 
        and adds it to the set.
        """
        obj_id = DEFAULT_INFRA_ID  
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

    def _calculate_shortest_paths(self, graph: nx.Graph) -> Dict[Any, Any]:
        """Internal helper to calculate paths on a specific graph instance."""
        # Filter active nodes
        active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]

        if not active_nodes:
            return {}

        def filter_node(n):
            return n in active_nodes
            
        def filter_edge(u, v):
            return graph.edges[u, v].get('enable', True)

        active_subgraph = nx.subgraph_view(graph, filter_node=filter_node, filter_edge=filter_edge)
        try:
            return dict(nx.all_pairs_dijkstra_path_length(active_subgraph, weight='delay'))
        except Exception as e:
            logger.error(f"Path calculation failed: {e}")
            return {}

    def update_shortest_paths(self, infra_id: str = DEFAULT_INFRA_ID) -> None:
        """Recalculates shortest paths for the specific infrastructure item."""
        item = self.infrastructures.get(infra_id)
        if item:
            item['shortest_paths'] = self._calculate_shortest_paths(item['graph'])

    def get_active_nodes(self, infra_id: str = DEFAULT_INFRA_ID) -> List[Any]:
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

    def get_active_edges(self, infra_id: str = DEFAULT_INFRA_ID) -> List[Tuple[Any, Any]]:
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
        
    def get_closest_edge_node(self, pos: Tuple[float, float], infra_id: str = DEFAULT_INFRA_ID) -> Optional[int]:
        graph = self.get_main_graph()
        if not graph: return None
        
        edge_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') == 'edge' and d.get('enable', True)]
        if not edge_nodes:
            edge_nodes = [n for n, d in graph.nodes(data=True) if d.get('layer') == 'edge' and d.get('enable', True)]
        if not edge_nodes:
            edge_nodes = [n for n, d in graph.nodes(data=True) if d.get('enable', True)]
        if not edge_nodes:
            return None
            
        distances = [np.linalg.norm(np.array(pos) - np.array(graph.nodes[n].get('pos', (0.5,0.5)))) for n in edge_nodes]
        return int(edge_nodes[np.argmin(distances)])

    def selectRandomGraphNodeByCentrality(self, centrality: float, sim_set: Any, node: Optional[int] = None) -> Optional[int]:
        graph = self.get_main_graph()
        if not graph: return None
        
        selected_nodes = [n for n, data in graph.nodes(data=True) if data.get('betweenness_centrality', 0) <= centrality and n != node]

        if selected_nodes:
            rng = sim_set.rng_graph
            selected_node = rng.choice(selected_nodes)
            return int(selected_node)
        return None

    def disable_node(self, object_id: int, sim_set: Any, event_set: Any, distribution_to_enable_node: str = '10', **kwargs: Any) -> Optional[str]:
        """Disables a specific node in the graph and schedules revival."""
        infra_id = DEFAULT_INFRA_ID
        node_id = object_id

        item = self.infrastructures.get(infra_id)
        if item and node_id in item['graph'].nodes:
            item['graph'].nodes[node_id]['enable'] = False

            # Clear the running applications and reset RAM to 0
            item['graph'].nodes[node_id]['running_applications'] = []
            item['graph'].nodes[node_id]['ram_used'] = 0.0

            self.update_shortest_paths(infra_id)

            # Schedule Revival
            distribution_to_enable_node = sim_set.parse_distribution(distribution_to_enable_node, context='graph')

            eventAttributes = event_set.newEventItem(
                object_id=node_id,
                type_object='graph_node',
                time=distribution_to_enable_node + event_set.global_time,
                action='revive_node',
                impact={'event_set': None, 'associated_event_id': None}
            )
            associated_event_id = event_set.add_event(eventAttributes, sim_set=sim_set)
            event_set.events[associated_event_id]['impact']['associated_event_id'] = associated_event_id

            return f"Node {node_id} has been disabled. Scheduled revival in {distribution_to_enable_node + event_set.global_time} time units."
        else:
            logger.warning(f"Node {node_id} not found in graph {infra_id}.")
            return None

    def revive_node(self, object_id: int, event_set: Any, associated_event_id: str, **kwargs: Any) -> str:
        """Revives a node in the graph and updates paths."""
        infra_id = DEFAULT_INFRA_ID
        node_id = object_id

        item = self.infrastructures.get(infra_id)
        if item and node_id in item['graph'].nodes:
            item['graph'].nodes[node_id]['enable'] = True
            self.update_shortest_paths(infra_id)
        else:
            logger.warning(f"Node {node_id} not found in graph {infra_id}.")
        
        if event_set and associated_event_id:
            event_set.remove_event(associated_event_id)

        return f"Node {node_id} has been revived."

    def disable_edge(self, object_id: Tuple[Any, Any], sim_set: Any, event_set: Any, distribution_to_enable_edge: str = '10', **kwargs: Any) -> Optional[str]:
        """Disables a specific edge in the graph and schedules revival."""
        infra_id = DEFAULT_INFRA_ID
        edge = object_id

        item = self.infrastructures.get(infra_id)
        if item and edge and item['graph'].has_edge(*edge):
            item['graph'].edges[edge]['enable'] = False
            self.update_shortest_paths(infra_id)

            # Schedule Revival
            distribution_to_enable_edge = sim_set.parse_distribution(distribution_to_enable_edge, context='graph')

            eventAttributes = event_set.newEventItem(
                object_id=edge,
                type_object='graph_edge',
                time=distribution_to_enable_edge + event_set.global_time,
                action='revive_edge',
                impact={'event_set': None, 'associated_event_id': None}
            )
            associated_event_id = event_set.add_event(eventAttributes, sim_set=sim_set)
            event_set.events[associated_event_id]['impact']['associated_event_id'] = associated_event_id

            return f"Edge {edge} has been disabled. Scheduled revival in {distribution_to_enable_edge + event_set.global_time} time units."
        else:
            logger.warning(f"Edge {edge} not found in graph {infra_id}.")
            return None

    def revive_edge(self, object_id: Tuple[Any, Any], event_set: Any, associated_event_id: str, **kwargs: Any) -> str:
        """Revives an edge in the graph and updates paths."""
        infra_id = DEFAULT_INFRA_ID
        edge = object_id

        item = self.infrastructures.get(infra_id)
        if item and edge and item['graph'].has_edge(*edge):
            item['graph'].edges[edge]['enable'] = True
            self.update_shortest_paths(infra_id)
        else:
            logger.warning(f"Edge {edge} not found in graph {infra_id}.")
            
        if event_set and associated_event_id:
            event_set.remove_event(associated_event_id)
            
        return f"Edge {edge} has been revived."

    def apply_placement(self, placement: Dict[str, Any], application_set: Any, infra_id: str = DEFAULT_INFRA_ID) -> None:
        """Updates the graph nodes state based on the placement dictionary."""
        item = self.infrastructures.get(infra_id)
        if not item: return
        graph = item['graph']
        
        active_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get('enable', True)]
        for node in active_nodes:
            graph.nodes[node]['ram_used'] = 0.0
            graph.nodes[node]['running_applications'] = []

        all_apps = application_set.get_all_apps()
        
        for app_name, ms_placements in placement.items():
            app_id, app_data_ref = None, None
            for a_id, app_data in all_apps.items():
                if app_data['name'] == app_name:
                    app_id, app_data_ref = a_id, app_data
                    break
            
            if app_id and app_data_ref and isinstance(ms_placements, dict):
                for ms_id, node in ms_placements.items():
                    if node in graph.nodes:
                        ms_ram = next((ms['ram'] for ms in app_data_ref.get('microservices', []) if ms['id'] == ms_id), 0.0)
                        graph.nodes[node]['ram_used'] += ms_ram
                        if app_id not in graph.nodes[node]['running_applications']:
                            graph.nodes[node]['running_applications'].append(app_id)

    def degrade_node(self, object_id: int, sim_set: Any, event_set: Any, p_loss_dist: str = '{"type": "beta", "a": 2, "b": 5}', distribution_to_restore_node: str = '10', **kwargs: Any) -> Optional[str]:
        """Degrades a specific node's computational capacity."""
        infra_id = DEFAULT_INFRA_ID
        node_id = object_id
        
        item = self.infrastructures.get(infra_id)
        if item and node_id in item['graph'].nodes:
            p_loss = sim_set.parse_distribution(p_loss_dist, context='graph')
            if p_loss is None: p_loss = 0.2
            
            node = item['graph'].nodes[node_id]
            target_attributes = kwargs.get('target_attributes', ['ram', 'cpu'])
            for attr in target_attributes:
                if attr in node:
                    if f'nominal_{attr}' not in node: 
                        node[f'nominal_{attr}'] = node.get(attr, 0.0)
                    node[attr] = round(node[f'nominal_{attr}'] * (1 - p_loss), 2)

            # Schedule Restoration
            distribution_to_restore_node = sim_set.parse_distribution(distribution_to_restore_node, context='graph')

            eventAttributes = event_set.newEventItem(
                object_id=node_id,
                type_object='graph_node',
                time=distribution_to_restore_node + event_set.global_time,
                action='restore_node',
                impact={'event_set': None, 'associated_event_id': None}
            )
            associated_event_id = event_set.add_event(eventAttributes, sim_set=sim_set)
            event_set.events[associated_event_id]['impact']['associated_event_id'] = associated_event_id

            return f"Node {node_id} degraded capacity by {p_loss*100:.1f}%. Scheduled restoration in {distribution_to_restore_node + event_set.global_time} time units. - Transient"
        else:
            logger.warning(f"Node {node_id} not found in graph {infra_id}.")
            return None

    def restore_node(self, object_id: int, event_set: Any, associated_event_id: str, **kwargs: Any) -> str:
        """Restores a node's nominal capacity."""
        infra_id = DEFAULT_INFRA_ID
        node_id = object_id
        item = self.infrastructures.get(infra_id)
        if item and node_id in item['graph'].nodes:
            node = item['graph'].nodes[node_id]
            nominal_keys = [k for k in list(node.keys()) if k.startswith('nominal_')]
            for k in nominal_keys:
                attr = k.replace('nominal_', '', 1)
                node[attr] = node[k]
                del node[k]
        else:
            logger.warning(f"Node {node_id} not found in graph {infra_id}.")
        
        if event_set and associated_event_id:
            event_set.remove_event(associated_event_id)

        return f"Node {node_id} capacity restored."

    def congest_edge(self, object_id: Tuple[Any, Any], sim_set: Any, event_set: Any, p_loss_dist: str = '{"type": "beta", "a": 2, "b": 5}', multiplier_dist: str = '{"type": "lognormal", "mean": 0.5, "sigma": 0.2}', distribution_to_clear_edge: str = '10', **kwargs: Any) -> Optional[str]:
        """Degrades a specific edge's bandwidth and latency."""
        infra_id = DEFAULT_INFRA_ID
        edge = object_id
        
        item = self.infrastructures.get(infra_id)
        if item and edge and item['graph'].has_edge(*edge):
            p_loss = sim_set.parse_distribution(p_loss_dist, context='graph')
            if p_loss is None: p_loss = 0.2
            multiplier = sim_set.parse_distribution(multiplier_dist, context='graph')
            if multiplier is None: multiplier = 1.5
            multiplier = max(1.01, multiplier)

            edge_data = item['graph'].edges[edge[0], edge[1]]
            
            target_attributes_loss = kwargs.get('target_attributes_loss', ['bw', 'prb'])
            target_attributes_mult = kwargs.get('target_attributes_multiplier', ['latency'])
            
            for attr in target_attributes_loss:
                if attr in edge_data:
                    if f'nominal_{attr}' not in edge_data: 
                        edge_data[f'nominal_{attr}'] = edge_data.get(attr, 0.0)
                    edge_data[attr] = round(edge_data[f'nominal_{attr}'] * (1 - p_loss), 2)
                    
            for attr in target_attributes_mult:
                if attr in edge_data:
                    if f'nominal_{attr}' not in edge_data: 
                        edge_data[f'nominal_{attr}'] = edge_data.get(attr, 0.0)
                    edge_data[attr] = round(edge_data[f'nominal_{attr}'] * multiplier, 2)
            
            self.update_shortest_paths(infra_id)

            distribution_to_clear_edge = sim_set.parse_distribution(distribution_to_clear_edge, context='graph')

            eventAttributes = event_set.newEventItem(
                object_id=edge,
                type_object='graph_edge',
                time=distribution_to_clear_edge + event_set.global_time,
                action='clear_edge',
                impact={'event_set': None, 'associated_event_id': None}
            )
            associated_event_id = event_set.add_event(eventAttributes, sim_set=sim_set)
            event_set.events[associated_event_id]['impact']['associated_event_id'] = associated_event_id

            return f"Edge {edge} congested (BW loss: {p_loss*100:.1f}%, Latency mult: {multiplier:.2f}x). Scheduled clearance in {distribution_to_clear_edge + event_set.global_time} time units. - Transient"
        else:
            logger.warning(f"Edge {edge} not found in graph {infra_id}.")
            return None

    def clear_edge(self, object_id: Tuple[Any, Any], event_set: Any, associated_event_id: str, **kwargs: Any) -> str:
        """Restores an edge's nominal bandwidth and latency."""
        infra_id = DEFAULT_INFRA_ID
        edge = object_id
        
        item = self.infrastructures.get(infra_id)
        if item and edge and item['graph'].has_edge(*edge):
            edge_data = item['graph'].edges[edge[0], edge[1]]
            nominal_keys = [k for k in list(edge_data.keys()) if k.startswith('nominal_')]
            for k in nominal_keys:
                attr = k.replace('nominal_', '', 1)
                edge_data[attr] = edge_data[k]
                del edge_data[k]
            self.update_shortest_paths(infra_id)
        else:
            logger.warning(f"Edge {edge} not found in graph {infra_id}.")
            
        if event_set and associated_event_id:
            event_set.remove_event(associated_event_id)
            
        return f"Edge {edge} congestion cleared."

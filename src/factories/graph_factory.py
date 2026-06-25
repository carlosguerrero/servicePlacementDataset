import networkx as nx
import numpy as np
import logging
from typing import Any, Dict, Optional

from ..infrastructure import InfrastructureSet
from ..eventSet import generate_events
from ..constants import (
    DEFAULT_NUM_NODES, DEFAULT_MIN_RAM, 
    DEFAULT_MAX_RAM, DEFAULT_TREE_BRANCHING_R, DEFAULT_TREE_BRANCHING_H
)

logger = logging.getLogger(__name__)

def _generate_random_graph(config: Dict[str, Any], event_set: Any, sim_set: Any) -> Optional[InfrastructureSet]:
    """Internal function to handle the 'random' generation mode."""
    infra_config = config.get('infrastructure', {})
    model_params = infra_config.get('model', {})
    
    model_name = model_params.get('name', 'barabasi_albert')
    num_nodes = infra_config.get('num_nodes', DEFAULT_NUM_NODES)
    
    logger.info(f"Generating {model_name} graph with {num_nodes} nodes...")

    seed_graph_creation = sim_set.rng_graph

    if model_name == 'erdos_renyi':
        p = model_params.get('p', 0.1)
        temp_graph = nx.erdos_renyi_graph(num_nodes, p, seed=seed_graph_creation)
    elif model_name == 'scale_free':
        m = model_params.get('m', 2)
        if m >= num_nodes: m = 1
        temp_graph = nx.barabasi_albert_graph(num_nodes, m, seed=seed_graph_creation)
    elif model_name == 'spatial':
        radius = model_params.get('radius', 0.1)
        temp_graph = nx.random_geometric_graph(num_nodes, radius, seed=seed_graph_creation)
    elif model_name == 'fat_tree' or model_name == 'tree':
        r = model_params.get('branching_r', DEFAULT_TREE_BRANCHING_R) 
        h = model_params.get('branching_h', DEFAULT_TREE_BRANCHING_H)
        temp_graph = nx.balanced_tree(r, h)
        
        # Calculate depth from root (node 0) for depth_based_layer mode
        depths = nx.single_source_shortest_path_length(temp_graph, 0)
        for node_id, d in depths.items():
            temp_graph.nodes[node_id]['depth'] = d
            
    elif model_name == 'multi_tier':
        # Layer percentages
        cloud_pct = model_params.get('cloud', {}).get('percentage', 2)
        fog_pct = model_params.get('fog', {}).get('percentage', 18)
        
        N_c = max(1, int(num_nodes * cloud_pct / 100))
        N_f = max(1, int(num_nodes * fog_pct / 100))
        N_e = max(1, num_nodes - N_c - N_f)
        
        # Cloud: Complete Graph
        G_c = nx.complete_graph(N_c)
        for n in G_c.nodes(): G_c.nodes[n]['layer'] = 'cloud'
            
        # Fog: Scale-Free
        m_fog = model_params.get('fog', {}).get('m', 2)
        if m_fog >= N_f: m_fog = max(1, N_f - 1)
        G_f = nx.barabasi_albert_graph(N_f, m_fog, seed=seed_graph_creation)
        for n in G_f.nodes(): G_f.nodes[n]['layer'] = 'fog'
        
        # Edge: Spatial
        radius_edge = model_params.get('edge', {}).get('radius', 0.1)
        G_e = nx.random_geometric_graph(N_e, radius_edge, seed=seed_graph_creation)
        for n in G_e.nodes(): G_e.nodes[n]['layer'] = 'edge'
        
        temp_graph = nx.Graph()
        
        # Offset and copy nodes. Cloud and Fog get random positions if spatial stitching is needed.
        for n, data in G_c.nodes(data=True):
            data['pos'] = (float(sim_set.rng_graph.random()), float(sim_set.rng_graph.random()))
            temp_graph.add_node(n, **data)
            
        offset_f = N_c
        for n, data in G_f.nodes(data=True):
            data['pos'] = (float(sim_set.rng_graph.random()), float(sim_set.rng_graph.random()))
            temp_graph.add_node(n + offset_f, **data)
            
        offset_e = N_c + N_f
        for n, data in G_e.nodes(data=True):
            temp_graph.add_node(n + offset_e, **data)
            
        # Add intra-layer edges
        for u, v in G_c.edges(): temp_graph.add_edge(u, v)
        for u, v in G_f.edges(): temp_graph.add_edge(u + offset_f, v + offset_f)
        for u, v in G_e.edges(): temp_graph.add_edge(u + offset_e, v + offset_e)
            
        # Stitch Fog to Cloud (Closest)
        cloud_nodes = list(G_c.nodes())
        fog_nodes = [n + offset_f for n in G_f.nodes()]
        for f_node in fog_nodes:
            f_pos = np.array(temp_graph.nodes[f_node]['pos'])
            distances = [np.linalg.norm(f_pos - np.array(temp_graph.nodes[c_node]['pos'])) for c_node in cloud_nodes]
            closest_c = cloud_nodes[np.argmin(distances)]
            temp_graph.add_edge(f_node, closest_c)
            
        # Stitch Edge to Fog (Closest)
        edge_nodes = [n + offset_e for n in G_e.nodes()]
        for e_node in edge_nodes:
            e_pos = np.array(temp_graph.nodes[e_node]['pos'])
            distances = [np.linalg.norm(e_pos - np.array(temp_graph.nodes[f_node]['pos'])) for f_node in fog_nodes]
            closest_f = fog_nodes[np.argmin(distances)]
            temp_graph.add_edge(e_node, closest_f)
    else:
        logger.error(f"Graph model '{model_name}' not recognized.")
        return None

    spatial_region = config.get('user', {}).get('spatial_region', {})
    width = spatial_region.get('width', 1.0)
    height = spatial_region.get('height', 1.0)
    
    if model_name not in ['multi_tier', 'spatial']:
        layout_seed = int(sim_set.rng_graph.integers(0, 100000)) if hasattr(sim_set.rng_graph, 'integers') else 42
        pos_dict = nx.spring_layout(temp_graph, seed=layout_seed)
        for n, p in pos_dict.items():
            normalized_x = (p[0] + 1) / 2.0
            normalized_y = (p[1] + 1) / 2.0
            temp_graph.nodes[n]['pos'] = (float(normalized_x * width), float(normalized_y * height))
    else:
        for n, data in temp_graph.nodes(data=True):
            if 'pos' not in data:
                data['pos'] = (float(sim_set.rng_graph.random()), float(sim_set.rng_graph.random()))
            data['pos'] = (float(data['pos'][0] * width), float(data['pos'][1] * height))

    # Calculate Centrality first so we can use it for centrality_based attributes
    if temp_graph.number_of_nodes() > 0:
        try:
            betweenness_centrality = nx.betweenness_centrality(temp_graph)
            for node, centrality in betweenness_centrality.items():
                temp_graph.nodes[node]['betweenness_centrality'] = round(centrality, 4)
        except Exception as e:
            logger.error(f"Could not calculate centrality: {e}")

    # Process node attributes
    node_attributes_config = infra_config.get('node', {}).get('attributes', {})
    
    # Inject layer config from model into the attributes loop
    layer_config = model_params.get('layer')
    if layer_config:
        node_attributes_config = dict(node_attributes_config) # copy
        node_attributes_config['layer'] = layer_config

    attr_keys = list(node_attributes_config.keys())
    if 'layer' in attr_keys:
        attr_keys.remove('layer')
        attr_keys.insert(0, 'layer')
        
    for attr_name in attr_keys:
        attr_config = node_attributes_config[attr_name]
        mode = attr_config.get('mode', 'homogenic')
        dist_config = attr_config.get('distribution', None)
        
        if mode == 'homogenic':
            # Generate values for all nodes
            if dist_config:
                if isinstance(dist_config, dict) and 'size' not in dist_config:
                    dist_config = dict(dist_config)
                    dist_config['size'] = num_nodes
                
                raw_values = sim_set.parse_distribution(dist_config, context='graph', num_nodes=num_nodes)
                
                if raw_values is not None:
                    if isinstance(raw_values, (int, float)):
                        raw_values = np.full(num_nodes, raw_values)
                        
                    min_val = attr_config.get('min')
                    max_val = attr_config.get('max')
                    if min_val is not None or max_val is not None:
                        raw_values = np.clip(raw_values, a_min=min_val, a_max=max_val)
                    raw_values = np.round(raw_values, decimals=2).tolist()
                    
                    for i, node_id in enumerate(temp_graph.nodes()):
                        layer_name = temp_graph.nodes[node_id].get('layer') or temp_graph.nodes[node_id].get('type')
                        if layer_name and layer_name in attr_config:
                            c_dist = attr_config[layer_name].get('distribution')
                            if c_dist:
                                val = sim_set.parse_distribution(c_dist, context='graph', num_nodes=num_nodes)
                                if val is not None:
                                    c_min = attr_config[layer_name].get('min')
                                    c_max = attr_config[layer_name].get('max')
                                    if c_min is not None or c_max is not None:
                                        val = np.clip(val, a_min=c_min, a_max=c_max)
                                    temp_graph.nodes[node_id][attr_name] = round(float(val), 2)
                                    continue
                        temp_graph.nodes[node_id][attr_name] = raw_values[i]
                        
        elif mode == 'centrality_based':
            centrality_type = attr_config.get('centrality_type', 'direct_proportional')
            for node_id in temp_graph.nodes():
                layer_name = temp_graph.nodes[node_id].get('layer') or temp_graph.nodes[node_id].get('type')
                if layer_name and layer_name in attr_config:
                    c_dist = attr_config[layer_name].get('distribution')
                    if c_dist:
                        val = sim_set.parse_distribution(c_dist, context='graph', num_nodes=num_nodes)
                        if val is not None:
                            c_min = attr_config[layer_name].get('min')
                            c_max = attr_config[layer_name].get('max')
                            if c_min is not None or c_max is not None:
                                val = np.clip(val, a_min=c_min, a_max=c_max)
                            temp_graph.nodes[node_id][attr_name] = round(float(val), 2)
                            continue

                base_value = sim_set.parse_distribution(dist_config, context='graph', num_nodes=num_nodes)
                if base_value is None:
                    continue
                    
                cent = temp_graph.nodes[node_id].get('betweenness_centrality', 0.5)
                # Ensure multiplier is not absolute 0
                mapped_cent = max(cent, 0.01)
                
                if centrality_type == 'direct_proportional':
                    weight = mapped_cent
                elif centrality_type == 'inverted_proportional':
                    weight = max(1.0 - mapped_cent, 0.01)
                else:
                    weight = 1.0
                
                final_val = base_value * weight
                min_val = attr_config.get('min')
                max_val = attr_config.get('max')
                if min_val is not None or max_val is not None:
                    final_val = np.clip(final_val, a_min=min_val, a_max=max_val)
                
                temp_graph.nodes[node_id][attr_name] = round(float(final_val), 2)
                
        elif mode == 'centrality_based_layer':
            thresholds = attr_config.get('thresholds', {})
            cloud_min = thresholds.get('cloud_min', 0.8)
            fog_min = thresholds.get('fog_min', 0.2)
            
            for node_id in temp_graph.nodes():
                if 'layer' in temp_graph.nodes[node_id]: continue
                
                cent = temp_graph.nodes[node_id].get('betweenness_centrality', 0.0)
                if cent >= cloud_min:
                    val = 'cloud'
                elif cent >= fog_min:
                    val = 'fog'
                else:
                    val = 'edge'
                temp_graph.nodes[node_id][attr_name] = val
                
        elif mode == 'depth_based_layer':
            thresholds = attr_config.get('thresholds', {})
            cloud_max = thresholds.get('cloud_max', 0)
            fog_max = thresholds.get('fog_max', 2)
            
            for node_id in temp_graph.nodes():
                if 'layer' in temp_graph.nodes[node_id]: continue
                
                depth = temp_graph.nodes[node_id].get('depth', 10) # default to high depth if not present
                if depth <= cloud_max:
                    val = 'cloud'
                elif depth <= fog_max:
                    val = 'fog'
                else:
                    val = 'edge'
                temp_graph.nodes[node_id][attr_name] = val
                
        elif mode == 'layered':
            layer_dists = attr_config.get('distributions', {})
            for node_id in temp_graph.nodes():
                node_layer = temp_graph.nodes[node_id].get('layer') or temp_graph.nodes[node_id].get('type') or 'edge'
                dist_for_node = layer_dists.get(node_layer)
                
                if not dist_for_node:
                    if layer_dists:
                        dist_for_node = list(layer_dists.values())[0]
                    else:
                        continue
                        
                val = sim_set.parse_distribution(dist_for_node, context='graph', num_nodes=num_nodes)
                if val is not None:
                    min_val = attr_config.get('min')
                    max_val = attr_config.get('max')
                    if min_val is not None or max_val is not None:
                        val = np.clip(val, a_min=min_val, a_max=max_val)
                    temp_graph.nodes[node_id][attr_name] = round(float(val), 2)

    for node_id in temp_graph.nodes():
        temp_graph.nodes[node_id]['enable'] = True

    # Process edge attributes
    edge_attributes_config = infra_config.get('edge', {}).get('attributes', {})
    for attr_name, attr_config in edge_attributes_config.items():
        mode = attr_config.get('mode', 'homogenic')
        dist_config = attr_config.get('distribution', None)
        
        if mode == 'homogenic':
            for u, v in temp_graph.edges():
                val = sim_set.parse_distribution(dist_config, context='graph', num_nodes=num_nodes)
                if val is not None:
                    min_val = attr_config.get('min')
                    max_val = attr_config.get('max')
                    if min_val is not None or max_val is not None:
                        val = np.clip(val, a_min=min_val, a_max=max_val)
                    temp_graph.edges[u, v][attr_name] = round(float(val), 2)
        elif mode == 'centrality_based':
            centrality_type = attr_config.get('centrality_type', 'direct_proportional')
            for u, v in temp_graph.edges():
                val = sim_set.parse_distribution(dist_config, context='graph', num_nodes=num_nodes)
                if val is not None:
                    cent_u = temp_graph.nodes[u].get('betweenness_centrality', 0.5)
                    cent_v = temp_graph.nodes[v].get('betweenness_centrality', 0.5)
                    avg_cent = (cent_u + cent_v) / 2.0
                    mapped_cent = max(avg_cent, 0.01)
                    
                    if centrality_type == 'direct_proportional':
                        weight = mapped_cent
                    elif centrality_type == 'inverted_proportional':
                        weight = max(1.0 - mapped_cent, 0.01)
                    else:
                        weight = 1.0
                    
                    final_val = val * weight
                    min_val = attr_config.get('min')
                    max_val = attr_config.get('max')
                    if min_val is not None or max_val is not None:
                        final_val = np.clip(final_val, a_min=min_val, a_max=max_val)
                    temp_graph.edges[u, v][attr_name] = round(float(final_val), 2)
        elif mode == 'layered':
            layer_dists = attr_config.get('distributions', {})
            fallback_dist = layer_dists.get('edge')
            if not fallback_dist and layer_dists:
                fallback_dist = list(layer_dists.values())[0]
            for u, v in temp_graph.edges():
                val = sim_set.parse_distribution(fallback_dist, context='graph', num_nodes=num_nodes)
                if val is not None:
                    min_val = attr_config.get('min')
                    max_val = attr_config.get('max')
                    if min_val is not None or max_val is not None:
                        val = np.clip(val, a_min=min_val, a_max=max_val)
                    temp_graph.edges[u, v][attr_name] = round(float(val), 2)

    for u, v in temp_graph.edges():
        temp_graph.edges[u, v]['enable'] = True

    graph_set = InfrastructureSet()
    
    # This creates the dictionary item {'DEFAULT_INFRA_ID': {graph:..., actions:...}}
    # We no longer pass global actions to the graph
    graph_item = graph_set.init_infrastructure(temp_graph, actions={})

    node_actions = infra_config.get('node', {}).get('actions', {})
    edge_actions = infra_config.get('edge', {}).get('actions', {})

    for node_id in temp_graph.nodes():
        node_item = {'id': node_id, 'actions': node_actions}
        generate_events(node_item, 'graph_node', event_set, sim_set)
        
    for edge in temp_graph.edges():
        edge_item = {'id': edge, 'actions': edge_actions}
        generate_events(edge_item, 'graph_edge', event_set, sim_set)
    
    return graph_set

# We can DELETE this function if we decide not to implement manual graph creation, but I left it here for now in case we want to add that feature later without much hassle
def _generate_manual_graph(config: Dict[str, Any]) -> InfrastructureSet:
    logger.info("Building graph from defined topology...")
    graph = InfrastructureSet()
    
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

def generate_infrastructure(config: Dict[str, Any], event_set: Any, sim_set: Any) -> InfrastructureSet:
    """
    Generates a random graph using the NetworkX library.

    Main entry point. Switches between manual and random generation
    based on the 'mode' setting in YAML.
        num_nodes (int): The number of nodes the graph will have.
        model (str, optional): The graph model to use.
                               Common options: 'erdos_renyi', 'barabasi_albert', 'watts_strogatz'.
                               Defaults to 'erdos_renyi'.
        **kwargs: Additional arguments to be passed to the model's generation function.
                   For example, for 'erdos_renyi', you can pass 'p' (edge probability).
                   For 'barabasi_albert', you can pass 'm' (number of edges to attach per new node).
                   For 'watts_strogatz', you can pass 'k' (initial number of neighbors),
                   'p' (rewiring probability), and 'n' (number of nodes, already passed separately).

    Returns:
        networkx.Graph: The randomly generated graph.
                        Returns None if the specified model is not valid.
    """
    setup = config.get('setup', {})
    mode = setup.get('mode', 'random')
    
    if mode == 'manual':
        # graph = _generate_manual_graph(config)
        pass
    else:
        graph_dict = _generate_random_graph(config, event_set, sim_set)
        graph = graph_dict.get_main_graph()

    return graph_dict

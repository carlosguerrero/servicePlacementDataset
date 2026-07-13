import networkx as nx
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

def _get_all_ids_by_type(type_object: str, app_set: Any, user_set: Any, infrastructure: Any) -> List[Any]:
    if type_object == 'app':
        return list(app_set.get_all_apps().keys())
    elif type_object == 'user':
        return list(user_set.get_all_users().keys())
    elif type_object == 'graph_node':
        graph = infrastructure.get_main_graph()
        return list(graph.nodes()) if graph else []
    elif type_object == 'graph_edge':
        graph = infrastructure.get_main_graph()
        return list(graph.edges()) if graph else []
    return []

def _get_node_proximity(origin_id: Any, candidates: List[Any], infrastructure: Any) -> List[Any]:
    graph = infrastructure.get_main_graph()
    if not graph or origin_id not in graph.nodes:
        return candidates

    def get_distance(node):
        try:
            return nx.shortest_path_length(graph, source=origin_id, target=node)
        except nx.NetworkXNoPath:
            return float('inf')
        except nx.NodeNotFound:
            return float('inf')

    return sorted(candidates, key=get_distance)

def _get_app_proximity(origin_id: Any, candidates: List[Any], app_set: Any) -> List[Any]:
    apps = app_set.get_all_apps()
    origin_app = apps.get(origin_id)
    if not origin_app:
        return candidates
        
    origin_popularity = origin_app.get('popularity', 0)
    origin_is_local = origin_app.get('local_app_ratio', 0) > 0
    
    # If local, proximity is whether they are also local (hotspot sharing)
    # If not local, proximity is popularity difference
    def get_distance(app_id):
        app_data = apps.get(app_id, {})
        app_is_local = app_data.get('local_app_ratio', 0) > 0
        if origin_is_local:
            return 0 if app_is_local else 1
        else:
            app_popularity = app_data.get('popularity', 0)
            return abs(origin_popularity - app_popularity)
            
    return sorted(candidates, key=get_distance)

def _get_user_proximity(origin_id: Any, candidates: List[Any], user_set: Any, infrastructure: Any) -> List[Any]:
    users = user_set.get_all_users()
    origin_user = users.get(origin_id)
    if not origin_user:
        return candidates
        
    origin_node = origin_user.get('connectedTo')
    graph = infrastructure.get_main_graph()
    if not graph:
        return candidates
    
    def get_distance(user_id):
        target_user = users.get(user_id, {})
        target_node = target_user.get('connectedTo')
        if origin_node == target_node:
            return 0
        if not origin_node or not target_node or origin_node not in graph.nodes or target_node not in graph.nodes:
            return float('inf')
        try:
            return nx.shortest_path_length(graph, source=origin_node, target=target_node)
        except nx.NetworkXNoPath:
            return float('inf')

    return sorted(candidates, key=get_distance)

def _get_proximity_sorted(origin_id: Any, candidates: List[Any], type_object: str, app_set: Any, user_set: Any, infrastructure: Any, sim_set: Optional[Any] = None) -> List[Any]:
    """Returns the candidates list sorted by proximity to the origin_id."""
    candidates = [c for c in candidates if c != origin_id]
    
    if type_object == 'graph_node':
        return _get_node_proximity(origin_id, candidates, infrastructure)
    elif type_object == 'app':
        return _get_app_proximity(origin_id, candidates, app_set)
    elif type_object == 'user':
        return _get_user_proximity(origin_id, candidates, user_set, infrastructure)
    
    if sim_set is not None:
        sim_set.shuffle('event', candidates)
    return candidates

def resolve_targets(first_event: Dict[str, Any], sub_action: Dict[str, Any], app_set: Any, user_set: Any, infrastructure: Any, sim_set: Any) -> List[Any]:
    """
    Resolves the target IDs for a specific sub-action based on target_resolution configurations.
    Returns a list of object_ids.
    """
    target_resolution = sub_action.get('impact_params', {}).get('target_resolution', {})
    
    # Retrocompatibility / Defaults
    if not isinstance(target_resolution, dict):
        mode = 'self' if not target_resolution else str(target_resolution)
        group_config = {}
    else:
        mode = target_resolution.get('mode', 'self')
        group_config = target_resolution.get('group_config', {})
        
    type_object = sub_action.get('type_object', first_event.get('type_object'))
    original_id = first_event.get('object_id')
    
    if mode == 'intelligent':
        # Delegate to handler
        return [original_id]
        
    if mode == 'id':
        return [target_resolution.get('id')]
        
    all_candidates = _get_all_ids_by_type(type_object, app_set, user_set, infrastructure)
    if not all_candidates:
        return []

    if mode == 'random':
        return [sim_set.choice('event', all_candidates)]
        
    if mode == 'self':
        if original_id is None:
             # If generated by global spawner, 'self' falls back to random
             return [sim_set.choice('event', all_candidates)]
             
        # Cross-entity exact match is not naturally supported by 'self' unless IDs match, 
        # but 'intelligent' is meant for cross-entity.
        if original_id in all_candidates:
            return [original_id]
        elif str(original_id) in all_candidates:
            return [str(original_id)]
        elif type(all_candidates[0])(original_id) in all_candidates:
            return [type(all_candidates[0])(original_id)]
        else:
            # Fallback
            return [sim_set.choice('event', all_candidates)]
            
    if mode == 'group':
        strategy = group_config.get('strategy', 'random')
        raw_num_elements = group_config.get('num_elements', 1)
        
        if isinstance(raw_num_elements, float) and 0.0 <= raw_num_elements <= 1.0:
            num_elements = max(1, int(len(all_candidates) * raw_num_elements))
        else:
            num_elements = int(raw_num_elements)
        
        if strategy == 'list':
            return group_config.get('list', [])[:num_elements]
            
        elif strategy == 'random':
            return sim_set.sample('event', all_candidates, min(num_elements, len(all_candidates)))
            
        elif strategy == 'self_random':
            res = []
            if original_id in all_candidates:
                res.append(original_id)
            candidates = [c for c in all_candidates if c != original_id]
            needed = num_elements - len(res)
            if needed > 0 and candidates:
                res.extend(sim_set.sample('event', candidates, min(needed, len(candidates))))
            return res
            
        elif strategy == 'self_proximity':
            res = []
            if original_id in all_candidates:
                res.append(original_id)
            else:
                # If the origin is not in candidates (e.g. cross-entity), pick random origin
                original_id = sim_set.choice('event', all_candidates)
                res.append(original_id)
                
            sorted_candidates = _get_proximity_sorted(original_id, all_candidates, type_object, app_set, user_set, infrastructure, sim_set)
            needed = num_elements - len(res)
            if needed > 0:
                res.extend(sorted_candidates[:needed])
            return res
            
        elif strategy == 'random_proximity':
            origin = sim_set.choice('event', all_candidates)
            res = [origin]
            sorted_candidates = _get_proximity_sorted(origin, all_candidates, type_object, app_set, user_set, infrastructure, sim_set)
            needed = num_elements - len(res)
            if needed > 0:
                res.extend(sorted_candidates[:needed])
            return res

    return [original_id]

import random
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from .eventSet import EventSet, generate_events
from .userSet import UserSet, create_new_user

# Note: I just added the DESCOMENTAR line to indicate where the event generation for the graph would be triggered

class InvalidTopologyModelError(Exception):
    pass

class ApplicationSet:
    def __init__(self) -> None:
        self.applications: Dict[str, Dict[str, Any]] = {}
        # Initialize a counter to keep track of App IDs (App_0, App_1)
        self.app_counter: int = 0

    def getNextAppId(self) -> str:
        """Generates the next sequential application name."""
        name = f"App_{self.app_counter}"
        self.app_counter += 1
        return name

    def selectRandomAppByAggregatedPopularity(self, popularity: float) -> Optional[str]:
        """
        Selects a random application based on the aggregated popularity of the applications.

        Args:
            popularity (float): The aggregated popularity value to use for selection.

        Returns:
            str: The name of the selected application.
        """
        total_popularity = sum(app['popularity'] for app in self.applications.values())
        if total_popularity == 0:
            return None

        # Normalize the popularity values
        normalized_popularity = {app_id: app['popularity'] / total_popularity for app_id, app in self.applications.items()}

        # Select a random application based on the normalized popularity
        selected_app = random_app.choices(list(normalized_popularity.keys()), weights=normalized_popularity.values(), k=1)[0]
        return selected_app
    
    def selectRandomAppIdByPopularity(self, popularity: Optional[float], sim_set: Any) -> str:
        """Selects a random application based on its popularity."""
        if popularity is None:
            popularity = 0.0
        selected_apps = [app for app in self.applications.values() if app['popularity'] >= popularity]
        
        rng = sim_set.rng_app
        
        if selected_apps:
            rndApp = rng.choice(selected_apps)
            return rndApp['id']

        selected_apps = [app for app in self.applications.values()]
        
        rndApp = rng.choice(selected_apps)
        return rndApp['id']
        
    def select_app_for_user(self, user_pos: Tuple[float, float], pop_conf: Dict[str, Any], sim_set: Any) -> Optional[str]:
        app_list = list(self.applications.values())
        if not app_list:
            return None
            
        rng = sim_set.rng_user
        import numpy as np
        
        radius = pop_conf.get('local_radius_influence', 0.15)
        
        # Calculate dynamic probabilities
        probs = []
        for app in app_list:
            p = app['popularity']
            if app.get('is_local') and app.get('pos') is not None and user_pos is not None:
                dist = np.linalg.norm(np.array(user_pos) - np.array(app['pos']))
                if dist <= radius:
                    # Boost probability exponentially based on distance
                    p = p * np.exp(-dist / radius) * 10 # Boost factor
            probs.append(p)
            
        probs = np.array(probs)
        probs_sum = probs.sum()
        if probs_sum > 0:
            probs = probs / probs_sum
        else:
            probs = np.ones(len(app_list)) / len(app_list)
        
        selected_app = rng.choice(app_list, p=probs)
        return selected_app['id']

    def get_application_name_by_id(self, app_id: str) -> Optional[str]:   
        """Retrieves the name of an application by its ID."""
        app = self.applications.get(app_id)
        if app:
            return app['name']
        return None
       
    def get_application_ram_by_name(self, app_name: str) -> Optional[float]:
        """Retrieves the RAM requirement of an application by its name."""
        for app in self.applications.values():
            if app['name'] == app_name:
                return app['ram']
        return None

    def newAppItem(self, name: str, popularity: float, microservices: List[Dict[str, Any]], actions: Dict[str, Any], is_local: bool = False, pos: Optional[Tuple[float, float]] = None, bw: float = 0.0, l_max: float = 0.0, edges: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Creates a new application item with the given attributes."""
        # Calculate aggregated resources dynamically
        aggregated_resources = {}
        for ms in microservices:
            for k, v in ms.items():
                if k != 'id' and isinstance(v, (int, float)):
                    aggregated_resources[k] = aggregated_resources.get(k, 0.0) + v
                    
        total_cpu = aggregated_resources.get('cpu', 0.0)
        total_ram = aggregated_resources.get('ram', 0.0)

        return {
            'name': name,
            'popularity': popularity,
            'microservices': microservices,
            'cpu': total_cpu,
            'ram': total_ram,
            **aggregated_resources,
            'disk': aggregated_resources.get('disk', 0.0),
            'bw': bw,
            'l_max': l_max,
            'time': 0.0,
            'actions': actions,
            'is_local': is_local,
            'pos': pos,
            'edges': edges if edges is not None else []
        }

    def add_application(self, appAttributes: Dict[str, Any]) -> str:
        """Adds a new application to the set."""
        app_id = str(uuid.uuid4())  # Generates a unique identifier
        appAttributes['id'] = app_id
        self.applications[app_id] = appAttributes
        return app_id

    def remove_app(self, app_id: str, user_set: Any, event_set: Any, **kwargs: Any) -> Any:
        """Removes an application from the set based on its ID."""

        if app_id in self.applications:
            message2 = user_set.remove_user_by_requested_app(app_id, event_set=event_set)  # Remove users requesting this app
            message = f"Application {self.applications[app_id]['name']} has been removed, along with its associated events. {message2}"
            del self.applications[app_id]
            event_set.remove_events_by_object_id(app_id)

            return message
        return False
    
    def increase_popularity(self, app_id: str, sim_set: Any, user_set: Any, multiplier: str, **kwargs: Any) -> str:
        multiplier_val = sim_set.parse_distribution(multiplier, context='app')
        old_popularity = self.applications[app_id]['popularity']

        self.applications[app_id]['popularity'] = self.applications[app_id]['popularity'] * multiplier_val

        user_set.increase_request_ratio_by_requested_app(app_id, sim_set=sim_set, multiplier=multiplier)

        message = f"Popularity of app {self.applications[app_id]['name']} increased from {old_popularity} to {self.applications[app_id]['popularity']}"
        return message
    
    def decrease_popularity(self, app_id: str, sim_set: Any, user_set: Any, multiplier: str, **kwargs: Any) -> str: 
        multiplier_val = sim_set.parse_distribution(multiplier, context='app')
        old_popularity = self.applications[app_id]['popularity']

        self.applications[app_id]['popularity'] = self.applications[app_id]['popularity'] * multiplier_val

        user_set.decrease_request_ratio_by_requested_app(app_id, sim_set=sim_set, multiplier=multiplier)

        message = f"Popularity of app {self.applications[app_id]['name']} decreased from {old_popularity} to {self.applications[app_id]['popularity']}"
        return message

    def update_app(self, app_id: str, sim_set: Any, config: Any, **kwargs: Any) -> str:
        app = self.applications.get(app_id)
        if not app:
            return "Application not found for update_app."

        rng = sim_set.rng_app
        events_conf = kwargs
        
        sigma_footprint_val = sim_set.parse_distribution(events_conf.get('sigma_footprint'), context='app')
        sigma_footprint = float(sigma_footprint_val) if sigma_footprint_val is not None else 0.1
        
        sigma_net_val = sim_set.parse_distribution(events_conf.get('sigma_net'), context='app')
        sigma_net = float(sigma_net_val) if sigma_net_val is not None else 0.1
        
        p_topo_val = sim_set.parse_distribution(events_conf.get('p_topo'), context='app')
        p_topo = float(p_topo_val) if p_topo_val is not None else 0.15
        
        l_min_val = sim_set.parse_distribution(events_conf.get('l_min'), context='app')
        l_min = int(l_min_val) if l_min_val is not None else 2
        
        l_max_global_val = sim_set.parse_distribution(events_conf.get('l_max_global'), context='app')
        l_max_global = int(l_max_global_val) if l_max_global_val is not None else 6

        msg_parts = []

        # 1. Footprint Mutation
        for ms in app.get('microservices', []):
            delta_cpu = rng.normal(0, sigma_footprint)
            delta_ram = rng.normal(0, sigma_footprint)
            ms['cpu'] = round(max(0.01, ms['cpu'] * (1 + delta_cpu)), 2)
            ms['ram'] = round(max(0.01, ms['ram'] * (1 + delta_ram)), 2)
        app['cpu'] = sum(ms['cpu'] for ms in app.get('microservices', []))
        app['ram'] = sum(ms['ram'] for ms in app.get('microservices', []))
        msg_parts.append("Footprint mutated")

        # 2. Network Constraints Mutation
        if 'bw' in app and 'l_max' in app:
            delta_bw = rng.normal(0, sigma_net)
            delta_lmax = rng.normal(0, sigma_net)
            app['bw'] = round(max(1.0, app['bw'] * (1 + delta_bw)), 2)
            app['l_max'] = round(max(1.0, app['l_max'] * (1 + delta_lmax)), 2)
            msg_parts.append("Network mutated")

        # 3. SFC Topology Mutation
        architecture = config.get('app', {}).get('architecture', 'microservice')
        if architecture != 'monolithic':
            if rng.random() < p_topo:
                L = len(app.get('microservices', []))
                if rng.random() < 0.5:
                    # Insert
                    if L < l_max_global:
                        ms_cpu = rng.lognormal(mean=0.5, sigma=0.2)
                        ms_ram = rng.lognormal(mean=0.5, sigma=0.2)
                        new_ms = {
                            'id': f"{app['name']}_ms_new_{rng.integers(1000, 9999)}",
                            'cpu': round(float(ms_cpu), 2),
                            'ram': round(float(ms_ram), 2)
                        }
                        insert_idx = rng.integers(0, L + 1)
                        app['microservices'].insert(insert_idx, new_ms)
                        msg_parts.append(f"Topology mutated (inserted MS at {insert_idx})")
                else:
                    # Delete
                    if L > l_min:
                        del_idx = rng.integers(0, L)
                        app['microservices'].pop(del_idx)
                        msg_parts.append(f"Topology mutated (deleted MS at {del_idx})")

        return f"App {app['name']} updated: " + ", ".join(msg_parts)

    def _rank_swap(self, app_id1: str, app_id2: str) -> None:
        if app_id1 in self.applications and app_id2 in self.applications:
            pop1 = self.applications[app_id1]['popularity']
            pop2 = self.applications[app_id2]['popularity']
            self.applications[app_id1]['popularity'] = pop2
            self.applications[app_id2]['popularity'] = pop1

    def surge_popularity(self, app_id: str, sim_set: Any, event_set: Any, config: Any, **kwargs: Any) -> str:
        app = self.applications.get(app_id)
        if not app:
            return "App not found"
        
        rng = sim_set.rng_app
        events_conf = kwargs
        
        # Sort apps by popularity (highest first)
        sorted_apps = sorted(self.applications.items(), key=lambda x: x[1]['popularity'], reverse=True)
        # Find current rank (0-indexed)
        current_rank = next((i for i, (a_id, _) in enumerate(sorted_apps) if a_id == app_id), -1)
        
        # Pick a target rank (Top 1 to 5)
        target_rank = rng.integers(0, min(5, len(sorted_apps))) if len(sorted_apps) > 0 else 0
        target_app_id = sorted_apps[target_rank][0] if len(sorted_apps) > 0 else app_id

        if current_rank != target_rank and current_rank != -1:
            self._rank_swap(app_id, target_app_id)
            
            # Transient logic
            transient_prob_val = sim_set.parse_distribution(events_conf.get('transient_prob'), context='app')
            transient_prob = float(transient_prob_val) if transient_prob_val is not None else 0.7
            is_transient = rng.random() < transient_prob
            if is_transient:
                duration_val = sim_set.parse_distribution(events_conf.get('duration_dist'), context='app')
                duration = float(duration_val) if duration_val is not None else 10.0
                
                restore_event = event_set.newEventItem(
                    type_object='app',
                    object_id=app_id,
                    time=event_set.global_time + duration,
                    action='restore_popularity',
                    impact={'target_app_id': target_app_id}
                )
                event_set.add_event(restore_event)
                return f"Surged popularity of {app['name']} (swapped with {self.applications[target_app_id]['name']}) - Transient ({duration:.2f}s)"
            else:
                return f"Surged popularity of {app['name']} (swapped with {self.applications[target_app_id]['name']}) - Permanent"
        return f"Surge failed for {app['name']}"

    def drop_popularity(self, app_id: str, sim_set: Any, event_set: Any, config: Any, **kwargs: Any) -> str:
        app = self.applications.get(app_id)
        if not app:
            return "App not found"
        
        rng = sim_set.rng_app
        events_conf = kwargs
        
        sorted_apps = sorted(self.applications.items(), key=lambda x: x[1]['popularity'], reverse=True)
        current_rank = next((i for i, (a_id, _) in enumerate(sorted_apps) if a_id == app_id), -1)
        
        # Pick a target rank (Bottom 5)
        num_apps = len(sorted_apps)
        target_rank = rng.integers(max(0, num_apps - 5), num_apps) if num_apps > 0 else 0
        target_app_id = sorted_apps[target_rank][0] if num_apps > 0 else app_id

        if current_rank != target_rank and current_rank != -1:
            self._rank_swap(app_id, target_app_id)
            
            transient_prob_val = sim_set.parse_distribution(events_conf.get('transient_prob'), context='app')
            transient_prob = float(transient_prob_val) if transient_prob_val is not None else 0.7
            is_transient = rng.random() < transient_prob
            if is_transient:
                duration_val = sim_set.parse_distribution(events_conf.get('duration_dist'), context='app')
                duration = float(duration_val) if duration_val is not None else 10.0
                
                restore_event = event_set.newEventItem(
                    type_object='app',
                    object_id=app_id,
                    time=event_set.global_time + duration,
                    action='restore_popularity',
                    impact={'target_app_id': target_app_id}
                )
                event_set.add_event(restore_event)
                return f"Dropped popularity of {app['name']} (swapped with {self.applications[target_app_id]['name']}) - Transient ({duration:.2f}s)"
            else:
                return f"Dropped popularity of {app['name']} (swapped with {self.applications[target_app_id]['name']}) - Permanent"
        return f"Drop failed for {app['name']}"

    def restore_popularity(self, app_id: str, target_app_id: str, **kwargs: Any) -> str:
        if app_id in self.applications and target_app_id in self.applications:
            self._rank_swap(app_id, target_app_id)
            return f"Restored popularity of {self.applications[app_id]['name']} (swapped back with {self.applications[target_app_id]['name']})"
        return "Restore failed (app missing)"

    def geo_demand_shift(self, app_id: str, sim_set: Any, config: Any, **kwargs: Any) -> str:
        app = self.applications.get(app_id)
        if not app or not app.get('is_local') or app.get('pos') is None:
            return "App not found or not a local app"
        
        rng = sim_set.rng_app
        events_conf = kwargs
        
        jump_prob_val = sim_set.parse_distribution(events_conf.get('jump_prob'), context='app')
        jump_prob = float(jump_prob_val) if jump_prob_val is not None else 0.2
        
        shift_type = 'jump' if rng.random() < jump_prob else 'drift'
        
        if shift_type == 'jump':
            new_pos = (float(rng.random()), float(rng.random()))
            app['pos'] = new_pos
            return f"Geo demand jumped to ({new_pos[0]:.3f}, {new_pos[1]:.3f}) for {app['name']}"
        else:
            # Drift
            dx_val = sim_set.parse_distribution(events_conf.get('drift_dist'), context='app')
            dy_val = sim_set.parse_distribution(events_conf.get('drift_dist'), context='app')
            dx = float(dx_val) if dx_val is not None else 0.0
            dy = float(dy_val) if dy_val is not None else 0.0
            
            old_x, old_y = app['pos']
            new_x = max(0.0, min(1.0, old_x + dx))
            new_y = max(0.0, min(1.0, old_y + dy))
            app['pos'] = (float(new_x), float(new_y))
            return f"Geo demand drifted to ({new_x:.3f}, {new_y:.3f}) for {app['name']}"

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an application by its ID from the set."""
        return self.applications.get(app_id)

    def get_all_apps(self) -> Dict[str, Dict[str, Any]]:
        """Returns all applications in the set."""
        return self.applications
    
    def __str__(self) -> str:
        """Returns a string representation of the ApplicationSet (the applications dictionary)."""
        return str(self.applications)
    
    def __repr__(self) -> str:
        """Official string representation for developers (useful for debugging)."""
        return f"ApplicationSet(applications={self.applications})"
    
    def new_app(self, app_id: str, config: Any, app_set: Any, infrastructure: Any, user_set: Any, event_set: Any, sim_set: Any, num_new_users: str, **kwargs: Any) -> str:
        """Creates a new app with random attributes based on the configuration."""
        num_new_users_val = sim_set.parse_distribution(num_new_users, context='app')

        create_new_app(config, app_set, event_set, sim_set)

        created_app_id = list(app_set.applications)[-1]

        for i in range(num_new_users_val):
            create_new_user(config, app_set, infrastructure, user_set, event_set, sim_set, created_app_id)

        message = f"Application {self.applications[created_app_id]['name']} has been created, along with {num_new_users_val} new users requesting this app."
        return message

def create_new_app(config: Dict[str, Any], application_set: ApplicationSet, event_set: EventSet, sim_set: Any) -> float:
    attributes = config
    app_conf = attributes.get('app', {})
    app_actions_config = app_conf.get('actions', {})
    services_conf = app_conf.get('services', app_conf.get('sfc', {}))
    pop_conf = app_conf.get('popularity', {})
    
    rng = sim_set.rng_app
    
    topology_model = services_conf.get('topology_model', 'sfc')
    if topology_model not in ['sfc', 'directed_scale_free']:
        raise InvalidTopologyModelError(f"Unsupported topology_model: {topology_model}")
    
    # 1. SFC/DAG Generation
    length_range = services_conf.get('length_range', [2, 6])
    if length_range[0] > length_range[1]:
        length_range = [2, 6] # Fallback
    chain_length = rng.integers(length_range[0], length_range[1] + 1)
    
    profiles = services_conf.get('profiles', {})
    if not profiles:
        # Default profile if not defined
        profiles = {
            'default': {
                'prob': 1.0,
                'cpu_lognorm': [0.5, 0.2],
                'ram_lognorm': [0.5, 0.2]
            }
        }
        
    profile_names = list(profiles.keys())
    profile_probs = [p.get('prob', 1.0) for p in profiles.values()]
    total_prob = sum(profile_probs)
    profile_probs = [p / total_prob for p in profile_probs]
    
    selected_profile_name = rng.choice(profile_names, p=profile_probs)
    selected_profile = profiles[selected_profile_name]
    
    attributes_def = selected_profile.get('attributes', {})
    
    microservices = []
    for i in range(chain_length):
        ms_item = {'id': f"{application_set.app_counter}_ms_{i}"}
        for attr_name, attr_config in attributes_def.items():
            dist_config = attr_config.get('distribution', attr_config)
            val = sim_set.parse_distribution(dist_config, context='app')
            if val is not None:
                ms_item[attr_name] = round(float(val), 2)
        microservices.append(ms_item)
        
    architecture = app_conf.get('architecture', 'microservice')
    if architecture == 'monolithic':
        mono_ms = {'id': f"{application_set.app_counter}_ms_mono"}
        for attr_name in attributes_def.keys():
            total_val = sum(ms.get(attr_name, 0.0) for ms in microservices)
            mono_ms[attr_name] = round(float(total_val), 2)
        microservices = [mono_ms]
    
    edges = []
    if architecture == 'microservice':
        if topology_model == 'sfc':
            for i in range(len(microservices) - 1):
                edges.append({'source': microservices[i]['id'], 'target': microservices[i+1]['id']})
        elif topology_model == 'directed_scale_free':
            scale_free_settings = services_conf.get('scale_free_settings', {})
            m0 = scale_free_settings.get('initial_nodes', 2)
            m = scale_free_settings.get('edges_per_node', 2)
            
            if m > m0:
                raise InvalidTopologyModelError("edges_per_node must be less than or equal to initial_nodes")
            
            # Initial base DAG
            for i in range(min(m0, len(microservices)) - 1):
                edges.append({'source': microservices[i]['id'], 'target': microservices[i+1]['id']})
                
            degrees = {ms['id']: 0 for ms in microservices}
            for e in edges:
                degrees[e['source']] += 1
                degrees[e['target']] += 1
                
            # Preferential attachment growth
            for i in range(m0, len(microservices)):
                new_node_id = microservices[i]['id']
                existing_nodes = [microservices[j]['id'] for j in range(i)]
                
                total_degree = sum(degrees[node] for node in existing_nodes)
                if total_degree == 0:
                    probs = [1.0 / len(existing_nodes)] * len(existing_nodes)
                else:
                    probs = [degrees[node] / total_degree for node in existing_nodes]
                
                num_edges_to_create = min(m, len(existing_nodes))
                targets = rng.choice(existing_nodes, size=num_edges_to_create, replace=False, p=probs)
                
                for target_id in targets:
                    # Target (existing node, capa inferior) points to new node to maintain DAG
                    edges.append({'source': target_id, 'target': new_node_id})
                    degrees[new_node_id] += 1
                    degrees[target_id] += 1
        
    # 2. Local vs Global App
    is_local = rng.random() < pop_conf.get('local_app_ratio', 0.3)
    pos = (float(rng.random()), float(rng.random())) if is_local else None

    # 3. Network Requirements
    net_conf = services_conf.get('network', {})
    bw = round(float(rng.uniform(net_conf.get('bw_min', 10.0), net_conf.get('bw_max', 100.0))), 2)
    l_max = round(float(rng.uniform(net_conf.get('l_max_min', 10.0), net_conf.get('l_max_max', 50.0))), 2)

    appAttributes = application_set.newAppItem(
        name=application_set.getNextAppId(),
        popularity=0.0, # Will be set by Zipf calculation later
        microservices=microservices,
        actions=app_actions_config,
        is_local=is_local,
        pos=pos,
        bw=bw,
        l_max=l_max,
        edges=edges
    )
    
    application_set.add_application(appAttributes)
    generate_events(appAttributes, 'app', event_set, sim_set)

    return appAttributes['ram']

def generate_random_apps(config: Dict[str, Any], event_set: EventSet, sim_set: Any, infrastructure: Any, num_apps: Optional[int] = None, saturation_percentage: Optional[float] = None) -> Tuple[ApplicationSet, UserSet]:
    """
    Generates a list of random applications with random resource requirements.

    Args:
        num_apps (int): The number of applications to generate.
        **kwargs: Additional arguments to customize the application generation.

    Returns:
        list: A list of dictionaries representing the generated applications.
    """
    application_set = ApplicationSet()
    user_set = UserSet()

    total_ram_available = sum(feat.get('ram', 0.0) for _, feat in infrastructure.get_main_graph().nodes(data=True))
    
    attributes = config
    app_conf = attributes.get('app', {})
    total_ram_occupied = 0

    
    # CASE when I am given the saturation percentage to generate the number of apps accordingly
    if saturation_percentage is not None:
        i=0
        created_total_ram = 0
        while total_ram_occupied < saturation_percentage: # and i < 10:
            app_ram =create_new_app(config, application_set, event_set, sim_set)
            created_total_ram += app_ram
            created_app_id = list(application_set.applications)[-1]

            num_users_per_app = sim_set.parse_distribution(app_conf.get('num_new_users', 1), context='app')
            if num_users_per_app is None:
                num_users_per_app = 0
            num_users_per_app = int(num_users_per_app)
            for _ in range(num_users_per_app):
                create_new_user(config, application_set, infrastructure, user_set, event_set, sim_set, created_app_id)

            total_ram_occupied = round((created_total_ram / total_ram_available if total_ram_available > 0 else 0)*100, 2)
            logger.info(f"Total RAM occupied after creating app {created_app_id}: {total_ram_occupied}%")

            i += 1


    # CASE when I am given the number of apps to generate
    elif num_apps is not None:
        num_users_per_app = sim_set.parse_distribution(app_conf.get('num_new_users', 1), context='app')
        if num_users_per_app is None:
            num_users_per_app = 0
        num_users_per_app = int(num_users_per_app)

        for _ in range(num_apps):
            create_new_app(config, application_set, event_set, sim_set)

            created_app_id = list(application_set.applications)[-1]

            for _ in range(num_users_per_app):
                create_new_user(config, application_set, infrastructure, user_set, event_set, sim_set, created_app_id)
    
    else:
        raise ValueError("Either num_apps or saturation_percentage must be provided to generate applications.")

    # Apply popularity distribution
    pop_conf = app_conf.get('popularity', {})
    dist_config = pop_conf.get('distribution')
    app_list = list(application_set.applications.values())
    num_created = len(app_list)
    
    if num_created > 0:
        if dist_config:
            # Parse custom distribution
            raw_popularities = []
            for _ in range(num_created):
                val = sim_set.parse_distribution(dist_config, context='app')
                raw_popularities.append(float(val) if val is not None else 1.0)
            
            # Sort descending to assign higher popularities to earlier application ranks
            raw_popularities.sort(reverse=True)
            
            sum_pop = sum(raw_popularities)
            if sum_pop > 0:
                normalized_pops = [p / sum_pop for p in raw_popularities]
            else:
                normalized_pops = [1.0 / num_created] * num_created
                
            for i, app in enumerate(app_list):
                app['popularity'] = normalized_pops[i]
        else:
            # Fallback to Zipf's Law for backwards compatibility
            alpha = pop_conf.get('alpha', 1.2)
            sum_zipf = sum(1.0 / (i**alpha) for i in range(1, num_created + 1))
            
            for i, app in enumerate(app_list):
                rank = i + 1
                app['popularity'] = (1.0 / (rank**alpha)) / sum_zipf

    return application_set, user_set

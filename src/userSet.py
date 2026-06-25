import random
import uuid
import numpy as np
import logging
import math
from .eventSet import EventSet, generate_events

random_users_seed_default = 42

class UserSet:
    def __init__(self):
        self.users = {}
        # Initialize a counter to keep track of User IDs (User_0, Usser_1)
        self.user_counter = 0
        self.hotspots = None

    def getNextUserId(self):
        """Generates the next sequential application name."""
        name = f"User_{self.user_counter}"
        self.user_counter += 1
        return name
    
    def newUserItem(self, name, requestedApp, appName, requestRatio, connectedTo, centrality, actions, pos=(0.0, 0.0), speed=0.01, coverage_radius=0.2, current_direction=None, current_sign=None, current_angle=None):
        """Creates a new user item with the given attributes."""
        return {
            'name': name,
            'requestedApp': requestedApp,
            'appName': appName,
            'requestRatio': requestRatio,
            'connectedTo': connectedTo,
            'centrality': centrality,
            'actions': actions,
            'pos': pos,
            'speed': speed,
            'coverage_radius': coverage_radius,
            'current_direction': current_direction,
            'current_sign': current_sign,
            'current_angle': current_angle
        }

    def getAllUsersByApp(self, appId):
        """Returns all users that requested a specific application."""
        return [user for user in self.users.values() if user['requestedApp'] == appId]
    
    def getAllUsersByNode(self, nodeId):
        """Returns all users connected to a specific node."""
        return [user for user in self.users.values() if user['connectedTo'] == nodeId]

    def add_user(self, userAttributes, sim_set=None):
        """Adds a new user to the set with a deterministic UUID."""
        if sim_set != None:
            rng = sim_set.rng_user
            random_bytes = rng.bytes(16)
            user_id = str(uuid.UUID(bytes=random_bytes))
        else:
            user_id = str(uuid.uuid4())
        userAttributes['id'] = user_id
        self.users[user_id] = userAttributes
        return user_id
    

    def remove_user_by_requested_app(self, requested_app, **kwargs):
        """Removes a user from the set based on their requested application."""
        list_of_deleted_users = []

        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                # del self.users[user_id]
                self.remove_user(user_id, **kwargs)
                list_of_deleted_users.append(user_id)
            
        message = f"Users {list_of_deleted_users} have been removed due to their requested app."
        return message
    
    def remove_user(self, user_id, **kwargs):
        """Removes a user from the set based on its ID from the user_set and the event_set"""
        

        event_set = kwargs.get('event_set')

        if user_id in self.users:
            message = f"User '{self.users[user_id]['name']}' has been removed."

            del self.users[user_id]
            event_set.remove_events_by_object_id(user_id)
            return message
        return False
    
    def move_user(self, user_id, **kwargs):
        if user_id in self.users:
            user = self.users[user_id]
            infrastructure = kwargs.get('infrastructure')
            coverage_radius = user.get('coverage_radius', 0.2)
            config = kwargs.get('config', {})
            sim_set = kwargs.get('sim_set')
            
            spatial_region = config.get('user', {}).get('spatial_region', {})
            width = spatial_region.get('width', 1.0)
            height = spatial_region.get('height', 1.0)
            
            mobility_model = config.get('user', {}).get('mobility', {}).get('model', 'manhattan')
            speed = user.get('speed', 0.01)
            
            rng = sim_set.rng_user if (sim_set and hasattr(sim_set, 'rng_user')) else __import__('random')
            
            if mobility_model == 'manhattan':
                _move_manhattan_with_intersections(user, speed, width, height, rng, config.get('user', {}))
            elif mobility_model in ['random_waypoint', 'random', 'aleatorio']:
                turn_probs = config.get('user', {}).get('mobility', {}).get('turn_probabilities', {})
                p_straight = turn_probs.get('straight', 0.33)
                
                angle = user.get('current_angle')
                if angle is None or rng.random() > p_straight:
                    angle = rng.uniform(0, 2 * np.pi) if hasattr(rng, 'uniform') else rng.random() * 2 * np.pi
                    user['current_angle'] = float(angle)
                
                new_x = user['pos'][0] + speed * np.cos(angle)
                new_y = user['pos'][1] + speed * np.sin(angle)
                
                if new_x <= 0 or new_x >= width or new_y <= 0 or new_y >= height:
                    new_x = np.clip(new_x, 0.0, width)
                    new_y = np.clip(new_y, 0.0, height)
                    user['current_angle'] = float((angle + np.pi) % (2 * np.pi))
                    
                user['pos'] = (float(new_x), float(new_y))
            
            new_node = infrastructure.get_closest_edge_node(user['pos'])
            
            if new_node is not None:
                actual_graph = infrastructure.get_main_graph()
                n_pos = np.array(actual_graph.nodes[new_node].get('pos', (0.5, 0.5)))
                user_pos = np.array(user['pos'])
                dist = np.linalg.norm(user_pos - n_pos)
                
                old_node = user.get('connectedTo')
                user['connectedTo'] = new_node
                
                if coverage_radius is not None and dist > coverage_radius:
                    if user.get('status') != 'out_of_coverage':
                        return self.suspend_user(user_id, reason='out_of_coverage', **kwargs)
                    else:
                        return {
                            "message": f"User '{user['name']}' moved but remains out of coverage.",
                            "ap_changed": False,
                            "disconnected": True,
                            "old_node": old_node,
                            "new_node": new_node
                        }
                else:
                    reconnected = False
                    if user.get('status') == 'out_of_coverage':
                        self.reconnect_user(user_id, **kwargs)
                        reconnected = True
                
                ap_changed = (old_node != new_node)
                msg = f"User '{user['name']}' moved to node '{new_node}' (changed from '{old_node}')." if ap_changed else f"User '{user['name']}' moved but stayed connected to node '{new_node}'."
                
                return {
                    "message": msg,
                    "ap_changed": ap_changed,
                    "disconnected": False,
                    "reconnected": reconnected,
                    "old_node": old_node,
                    "new_node": new_node
                }
            return {
                "message": f"User '{user['name']}' stayed at node '{user['connectedTo']}' (no edge node available).",
                "ap_changed": False,
                "disconnected": False
            }
        return False
    
    def increase_request_ratio_by_requested_app(self, requested_app, **kwargs):
        """Removes a user from the set based on their requested application."""
        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                self.increase_request_ratio(user_id, **kwargs)

                message = f"Request ratio of user '{self.users[user_id]['name']}' increased due to requested app {requested_app}"
                return message
        return False
    
    def increase_request_ratio(self, user_id, **kwargs):
        
        sim_set = kwargs.get('sim_set')
        multiplier = sim_set.parse_distribution(kwargs.get('multiplier'), context='user')
        old_request_ratio = self.users[user_id]['requestRatio']
        self.users[user_id]['requestRatio'] = self.users[user_id]['requestRatio'] * multiplier

        message = f"Request ratio of user '{self.users[user_id]['name']}' increased from {old_request_ratio} to {self.users[user_id]['requestRatio']}"
        return message
    
    def decrease_request_ratio_by_requested_app(self, requested_app, **kwargs):
        """Removes a user from the set based on their requested application."""
        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                self.decrease_request_ratio(user_id, **kwargs)
                return True
        return False
    
    def decrease_request_ratio(self, user_id, **kwargs):
        
        sim_set = kwargs.get('sim_set')
        old_request_ratio = self.users[user_id]['requestRatio']
        multiplier = sim_set.parse_distribution(kwargs.get('multiplier'), context='user')
        self.users[user_id]['requestRatio'] = self.users[user_id]['requestRatio'] * multiplier

        message = f"Request ratio of user '{self.users[user_id]['name']}' decreased from {old_request_ratio} to {self.users[user_id]['requestRatio']}"
        return message

    def change_request_ratio(self, user_id, **kwargs):
        if user_id in self.users:
            sim_set = kwargs.get('sim_set')
            multiplier = sim_set.parse_distribution(kwargs.get('multiplier', '{"type": "uniform", "low": 0.5, "high": 2.0}'), context='user')
            if multiplier is None:
                multiplier = 1.0
            old_ratio = self.users[user_id].get('requestRatio', 1.0)
            self.users[user_id]['requestRatio'] = max(0.0, round(old_ratio * multiplier, 4))
            return f"User '{self.users[user_id]['name']}' request ratio changed from {old_ratio} to {self.users[user_id]['requestRatio']}."
        return False

    def get_user(self, user_id):
        """Retrieves a user by their ID from the set."""
        return self.users.get(user_id)

    def get_all_users(self):
        """Returns all users in the set."""
        return self.users

    def __str__(self):
        """Returns a string representation of the UserSet (the users dictionary)."""
        return str(self.users)

    def __repr__(self):
        """Official string representation for developers (useful for debugging)."""
        return f"UserSet(users={self.users})"
    
    def new_user(self, user_id, **kwargs):
        """Creates a new user with random attributes based on the configuration."""
        config = kwargs.get('config')
        app_set = kwargs.get('app_set')
        infrastructure = kwargs.get('infrastructure')
        user_set = kwargs.get('user_set')
        event_set = kwargs.get('event_set')
        sim_set = kwargs.get('sim_set')

        user_id = create_new_user(config, app_set, infrastructure, user_set, event_set, sim_set)

        message = f"User '{self.users[user_id]['name']}' has been created."
        return message



    def suspend_user(self, user_id, **kwargs):
        if user_id in self.users:
            reason = kwargs.get('reason', 'glitch')
            event_set = kwargs.get('event_set')
            sim_set = kwargs.get('sim_set')
            user = self.users[user_id]
            user['old_requestRatio'] = user.get('requestRatio', 1.0)
            user['requestRatio'] = 0.0
            
            if reason == 'out_of_coverage':
                user['status'] = 'out_of_coverage'
                return {
                    "message": f"User {self.users[user_id]['name']} out of coverage (suspended).",
                    "disconnected": True,
                    "reason": reason
                }
            else:
                user['status'] = 'suspended'
                distribution_to_resume = sim_set.parse_distribution(kwargs.get('distribution_to_resume_user', '10'), context='user') if sim_set else 10.0
                if event_set:
                    eventAttributes = event_set.newEventItem(
                        object_id=user_id,
                        type_object='user',
                        time=distribution_to_resume + event_set.global_time,
                        action='resume_user',
                        impact={'event_set': None, 'associated_event_id': None}
                    )
                    associated_event_id = event_set.add_event(eventAttributes)
                    event_set.events[associated_event_id]['impact']['associated_event_id'] = associated_event_id
                
                return {
                    "message": f"User {self.users[user_id]['name']} suspended ({reason}). Resuming in {distribution_to_resume} time units.",
                    "disconnected": True,
                    "reason": reason
                }
        return False
        
    def reconnect_user(self, user_id, **kwargs):
        if user_id in self.users:
            user = self.users[user_id]
            user['status'] = 'connected'
            if 'old_requestRatio' in user:
                user['requestRatio'] = user['old_requestRatio']
                del user['old_requestRatio']
            return {
                "message": f"User '{user['name']}' reconnected physically to coverage area.",
                "reconnected": True,
                "disconnected": False
            }
        return False
        
    def resume_user(self, user_id, **kwargs):
        if user_id in self.users:
            user = self.users[user_id]
            
            infrastructure = kwargs.get('infrastructure')
            coverage_radius = user.get('coverage_radius', 0.2)
            
            if 'pos' in user:
                new_node = infrastructure.get_closest_edge_node(user['pos']) if infrastructure else None
                
                out_of_coverage = True
                if new_node is not None:
                    actual_graph = infrastructure.get_main_graph()
                    n_pos = np.array(actual_graph.nodes[new_node].get('pos', (0.5, 0.5)))
                    user_pos = np.array(user['pos'])
                    dist = np.linalg.norm(user_pos - n_pos)
                    if coverage_radius is None or dist <= coverage_radius:
                        out_of_coverage = False
                        user['connectedTo'] = new_node
                
                event_set = kwargs.get('event_set')
                if event_set and 'associated_event_id' in kwargs:
                    assoc_id = kwargs['associated_event_id']
                    if assoc_id:
                        event_set.remove_event(assoc_id)
                        
                if out_of_coverage:
                    user['status'] = 'out_of_coverage'
                    return {
                        "message": f"User '{user['name']}' woke up but is out of coverage.",
                        "disconnected": True,
                        "reason": "out_of_coverage"
                    }
                else:
                    user['status'] = 'connected'
                    if 'old_requestRatio' in user:
                        user['requestRatio'] = user['old_requestRatio']
                        del user['old_requestRatio']
                    return {
                        "message": f"User '{user['name']}' resumed connection at {user.get('pos')}.",
                        "reconnected": True,
                        "disconnected": False
                    }
        return False
    
def _move_manhattan_with_intersections(user, distance, width, height, rng, user_conf):
    spatial_region = user_conf.get('spatial_region', {})
    N_v = spatial_region.get('num_vertical_streets', 10)
    N_h = spatial_region.get('num_horizontal_streets', 10)
    
    # Precompute streets
    X_streets = [i * (width / max(1, N_v - 1)) for i in range(N_v)] if N_v > 1 else [width / 2.0]
    Y_streets = [j * (height / max(1, N_h - 1)) for j in range(N_h)] if N_h > 1 else [height / 2.0]
    
    turn_probs = user_conf.get('mobility', {}).get('turn_probabilities', {'straight': 0.33, 'left': 0.33, 'right': 0.34})
    p_straight = turn_probs.get('straight', 0.33)
    p_left = turn_probs.get('left', 0.33)
    
    direction = user.get('current_direction')
    sign = user.get('current_sign')
    if not direction or not sign:
        direction = 'horizontal' if rng.random() > 0.5 else 'vertical'
        sign = 1 if rng.random() > 0.5 else -1
        
    pos_x, pos_y = user['pos']
    remaining_dist = distance
    
    loop_count = 0
    while remaining_dist > 0.0001 and loop_count < 100:
        loop_count += 1
        if direction == 'horizontal':
            next_x = pos_x + sign * remaining_dist
            crossings = [x for x in X_streets if min(pos_x, next_x) < x < max(pos_x, next_x)]
            if not crossings and (any(abs(next_x - x) < 1e-5 for x in X_streets)) and not any(abs(pos_x - x) < 1e-5 for x in X_streets):
                closest = min(X_streets, key=lambda x: abs(next_x - x))
                crossings = [closest]
            
            if crossings:
                crossings.sort(key=lambda x: abs(x - pos_x))
                intersection = crossings[0]
                
                dist_to_intersection = abs(intersection - pos_x)
                pos_x = intersection
                remaining_dist -= dist_to_intersection
                
                rand_val = rng.random()
                if rand_val < p_straight:
                    pass
                elif rand_val < p_straight + p_left:
                    direction = 'vertical'
                    sign = -1 if sign == 1 else 1
                else:
                    direction = 'vertical'
                    sign = 1 if sign == 1 else -1
            else:
                pos_x = next_x
                remaining_dist = 0
                
                if pos_x <= 0:
                    pos_x = 0
                    sign = 1
                elif pos_x >= width:
                    pos_x = width
                    sign = -1
        else: # vertical
            next_y = pos_y + sign * remaining_dist
            crossings = [y for y in Y_streets if min(pos_y, next_y) < y < max(pos_y, next_y)]
            if not crossings and (any(abs(next_y - y) < 1e-5 for y in Y_streets)) and not any(abs(pos_y - y) < 1e-5 for y in Y_streets):
                closest = min(Y_streets, key=lambda y: abs(next_y - y))
                crossings = [closest]
                
            if crossings:
                crossings.sort(key=lambda y: abs(y - pos_y))
                intersection = crossings[0]
                
                dist_to_intersection = abs(intersection - pos_y)
                pos_y = intersection
                remaining_dist -= dist_to_intersection
                
                rand_val = rng.random()
                if rand_val < p_straight:
                    pass
                elif rand_val < p_straight + p_left:
                    direction = 'horizontal'
                    sign = 1 if sign == 1 else -1
                else:
                    direction = 'horizontal'
                    sign = -1 if sign == 1 else 1
            else:
                pos_y = next_y
                remaining_dist = 0
                
                if pos_y <= 0:
                    pos_y = 0
                    sign = 1
                elif pos_y >= height:
                    pos_y = height
                    sign = -1
                    
    user['pos'] = (float(pos_x), float(pos_y))
    user['current_direction'] = direction
    user['current_sign'] = sign

def create_new_user(config, appsSet, infrastructure, user_set, event_set, sim_set, app_id = None):
    user_conf = config.get('user', {})
    user_actions_config = user_conf.get('actions', {})
    user_centrality=sim_set.parse_distribution(user_conf.get('centrality', '0.2'), context='user')
    rqApp = app_id if app_id is not None else appsSet.selectRandomAppIdByPopularity(sim_set.parse_distribution(user_conf.get('request_popularity'), context='user'), sim_set)
    rng = sim_set.rng_user if sim_set else __import__('random')
    appNm=appsSet.get_application(rqApp)['name']
    
    speed_dist = user_conf.get('mobility', {}).get('speed', 0.01)
    speed_val = sim_set.parse_distribution(speed_dist, context='user') if sim_set and isinstance(speed_dist, dict) else (speed_dist if not isinstance(speed_dist, dict) else 0.01)
    
    radius_dist = user_conf.get('mobility', {}).get('coverage_radius', 0.2)
    radius_val = sim_set.parse_distribution(radius_dist, context='user') if sim_set and isinstance(radius_dist, dict) else (radius_dist if not isinstance(radius_dist, dict) else 0.2)
    
    spatial_region = user_conf.get('spatial_region', {})
    width = spatial_region.get('width', 1.0)
    height = spatial_region.get('height', 1.0)

    spatial_dist = user_conf.get('spatial_distribution', {})
    spatial_model = spatial_dist.get('model', 'random_uniform')
    
    if spatial_model == 'thomas_cluster':
        if getattr(user_set, 'hotspots', None) is None:
            num_hotspots = spatial_dist.get('hotspots', 5)
            user_set.hotspots = [(float(rng.random() * width), float(rng.random() * height)) for _ in range(num_hotspots)]
        
        spread = spatial_dist.get('spread', 0.05)
        chosen_hotspot = rng.choice(user_set.hotspots)
        
        if hasattr(rng, 'normal'):
            new_x = chosen_hotspot[0] + rng.normal(0, spread)
            new_y = chosen_hotspot[1] + rng.normal(0, spread)
        else:
            new_x = chosen_hotspot[0] + __import__('random').gauss(0, spread)
            new_y = chosen_hotspot[1] + __import__('random').gauss(0, spread)
            
        new_x = np.clip(new_x, 0.0, width)
        new_y = np.clip(new_y, 0.0, height)
        initial_pos = (float(new_x), float(new_y))
    else:
        initial_pos = (float(rng.random() * width), float(rng.random() * height))
        
    if user_conf.get('mobility', {}).get('model') == 'manhattan':
        N_v = spatial_region.get('num_vertical_streets', 10)
        N_h = spatial_region.get('num_horizontal_streets', 10)
        X_streets = [i * (width / max(1, N_v - 1)) for i in range(N_v)] if N_v > 1 else [width / 2.0]
        Y_streets = [j * (height / max(1, N_h - 1)) for j in range(N_h)] if N_h > 1 else [height / 2.0]
        
        closest_x = min(X_streets, key=lambda x: abs(x - initial_pos[0]))
        d_x = abs(closest_x - initial_pos[0])
        
        closest_y = min(Y_streets, key=lambda y: abs(y - initial_pos[1]))
        d_y = abs(closest_y - initial_pos[1])
        
        if d_x < d_y:
            initial_pos = (float(closest_x), initial_pos[1])
            user_direction = 'vertical'
        else:
            initial_pos = (initial_pos[0], float(closest_y))
            user_direction = 'horizontal'
            
        user_sign = 1 if rng.random() > 0.5 else -1
        user_angle = None
    elif user_conf.get('mobility', {}).get('model') in ['random_waypoint', 'random', 'aleatorio']:
        user_direction = None
        user_sign = None
        user_angle = rng.uniform(0, 2 * np.pi) if hasattr(rng, 'uniform') else rng.random() * 2 * np.pi
    else:
        user_direction = None
        user_sign = None
        user_angle = None
        
    userAttributes = user_set.newUserItem(
        name=user_set.getNextUserId(),
        requestedApp=rqApp,  # Randomly select an application based on popularity
        appName=appNm,
        requestRatio=sim_set.parse_distribution(user_conf.get('request_ratio'), context='user') if sim_set else 1.0,  
        connectedTo=infrastructure.selectRandomGraphNodeByCentrality(user_centrality, sim_set),  # Randomly select a node from the graph
        centrality=user_centrality,
        actions=user_actions_config,
        pos=initial_pos,
        speed=speed_val,
        coverage_radius=radius_val,
        current_direction=user_direction,
        current_sign=user_sign,
        current_angle=user_angle
    )
    
    user_id = user_set.add_user(userAttributes, sim_set)
    generate_events(userAttributes, 'user', event_set, sim_set)

    return user_id

def generate_random_users(config, appsSet, infrastructure, event_set, sim_set):
    """
    Generates a list of random users with random application requests.

    Args:
        num_users (int): The number of users to generate.
        **kwargs: Additional arguments to customize the user generation.

    Returns:
        list: A list of dictionaries representing the generated users.
    """
    user_set = UserSet()

    attributes = config.get('attributes', {})
    user_conf = attributes.get('user', {})
    num_users = user_conf.get('num_users', 2)

    # Create some users in the set.
    for i in range(num_users):
        create_new_user(config, appsSet, infrastructure, user_set, event_set, sim_set)

    return user_set

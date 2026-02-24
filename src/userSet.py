import random
import uuid
from .utils.auxiliar_functions import get_random_from_range, selectRandomGraphNodeByCentrality, selectRandomAction, selectAdjacentNodeWhenMoving
from .eventSet import EventSet, generate_events

class UserSet:
    def __init__(self):
        self.users = {}
        # Initialize a counter to keep track of User IDs (User_0, Usser_1)
        self.user_counter = 0

    def getNextUserId(self):
        """Generates the next sequential application name."""
        name = f"User_{self.user_counter}"
        self.user_counter += 1
        return name
    
    def newUserItem(self, name, requestedApp, appName, requestRatio, connectedTo, centrality, actions):
        """Creates a new user item with the given attributes."""
        return {
            'name': name,
            'requestedApp': requestedApp,
            'appName': appName,
            'requestRatio': requestRatio,
            'connectedTo': connectedTo,
            'centrality': centrality,
            'actions': actions 
        }

    def getAllUsersByApp(self, appId):
        """Returns all users that requested a specific application."""
        return [user for user in self.users.values() if user['requestedApp'] == appId]
    
    def getAllUsersByNode(self, nodeId):
        """Returns all users connected to a specific node."""
        return [user for user in self.users.values() if user['connectedTo'] == nodeId]

    def add_user(self, userAttributes):
        """Adds a new user to the set."""
        user_id = str(uuid.uuid4()) 
        userAttributes['id'] = user_id
        self.users[user_id] = userAttributes
        return user_id

    def remove_user_by_requested_app(self, requested_app, params):
        """Removes a user from the set based on their requested application."""
        list_of_deleted_users = []

        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                # del self.users[user_id]
                self.remove_user(user_id, params)
                list_of_deleted_users.append(user_id)
            
        message = f"Users {list_of_deleted_users} have been removed due to requested app {requested_app}"
        return message
    
    def remove_user(self, user_id, params):
        """Removes a user from the set based on its ID from the user_set and the event_set"""
        if params is None:
            params = {}

        event_set = params.get('event_set')

        if user_id in self.users:
            del self.users[user_id]
            event_set.remove_events_by_object_id(user_id)

            message = f"User {user_id} has been removed."
            return message
        return False
    
    def move_user(self, user_id, params=None):
        if params is None:
            params = {}

        if user_id in self.users:
            user_centrality = self.users[user_id]['centrality']
    
        infrastructure = params.get('infrastructure')

        if user_id in self.users and infrastructure is not None:
            current_node = self.users[user_id]['connectedTo']
            self.users[user_id]['connectedTo'] = selectAdjacentNodeWhenMoving(infrastructure, current_node, user_centrality)

            message = f"User {user_id} moved from node {current_node} to node {self.users[user_id]['connectedTo']}"
            return message
            
        return False
    
    def increase_request_ratio_by_requested_app(self, requested_app, params):
        """Removes a user from the set based on their requested application."""
        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                self.increase_request_ratio(user_id, params)

                message = f"Request ratio of user {user_id} increased due to requested app {requested_app}"
                return message
        return False
    
    def increase_request_ratio(self, user_id, params=None):
        if params is None:
            params = {}
        multiplier = eval(params.get('multiplier'))
        old_request_ratio = self.users[user_id]['requestRatio']
        self.users[user_id]['requestRatio'] = self.users[user_id]['requestRatio'] * multiplier

        message = f"Request ratio of user {user_id} increased from {old_request_ratio} to {self.users[user_id]['requestRatio']}"
        return message
    
    def decrease_request_ratio_by_requested_app(self, requested_app, params):
        """Removes a user from the set based on their requested application."""
        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                self.decrease_request_ratio(user_id, params)
                return True
        return False
    
    def decrease_request_ratio(self, user_id, params=None):
        if params is None:
            params = {}
        old_request_ratio = self.users[user_id]['requestRatio']
        multiplier = eval(params.get('multiplier'))
        self.users[user_id]['requestRatio'] = self.users[user_id]['requestRatio'] * multiplier

        message = f"Request ratio of user {user_id} decreased from {old_request_ratio} to {self.users[user_id]['requestRatio']}"
        return message

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
    
    def new_user(self, user_id, params):
        """Creates a new user with random attributes based on the configuration."""
        config = params.get('config')
        app_set = params.get('app_set')
        infrastructure = params.get('infrastructure')
        user_set = params.get('user_set')
        event_set = params.get('event_set')

        create_new_user(config, app_set, infrastructure, user_set, event_set)

        message = f"User {user_id} has been created."
        return message
    
def create_new_user(config, appsSet, infrastructure, user_set, event_set, app_id = None):
    attributes = config.get('attributes', {})
    user_conf = attributes.get('user', {})
    user_actions_config = user_conf.get('actions', {})
    user_centrality=eval(user_conf.get('centrality'))
    rqApp = app_id if app_id is not None else appsSet.selectRandomAppIdByPopularity(eval(user_conf.get('request_popularity')))
    appNm=appsSet.get_application(rqApp)['name']
    userAttributes = user_set.newUserItem(
        name=user_set.getNextUserId(),
        requestedApp=rqApp,  # Randomly select an application based on popularity
        appName=appNm,
        requestRatio=eval(user_conf.get('request_ratio')),  
        connectedTo=selectRandomGraphNodeByCentrality(infrastructure, user_centrality),  # Randomly select a node from the graph
        centrality=user_centrality,
        actions=user_actions_config
    )
    
    user_set.add_user(userAttributes)
    generate_events(userAttributes, 'user', event_set)

def generate_random_users(config, appsSet, infrastructure, event_set):
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
        create_new_user(config, appsSet, infrastructure, user_set, event_set)

    return user_set

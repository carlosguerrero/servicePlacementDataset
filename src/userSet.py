import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
########################################

import uuid
from utils import get_random_from_range, selectRandomGraphNodeByCentrality, selectRandomAction
from src import EventSet, generate_events

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
    
    def newUserItem(self, name, requestedApp, appName, requestRatio, connectedTo, actions):
        """Creates a new user item with the given attributes."""
        return {
            'name': name,
            'requestedApp': requestedApp,
            'appName': appName,
            'requestRatio': requestRatio,
            'connectedTo': connectedTo,
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

    def remove_user_by_requested_app(self, requested_app):
        """Removes a user from the set based on their requested application."""
        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                del self.users[user_id]
                return True
        return False
    
    def remove_user(self, user_id, params=None):
        """Removes a user from the set based on its ID."""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False
    
    # REVISAR: pendiente de definir
    def move_user(self, user_id, params=None):
        if params is not None:
            self.users[user_id]['connectedTo'] = params[0]


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

def generate_random_users(config, appsSet, infrastructure, events_list):
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
    user_actions_config = user_conf.get('actions', {})

    # Create some users in the set
    for i in range(num_users):
        rqApp=appsSet.selectRandomAppIdByPopularity(get_random_from_range(config, 'user', 'request_popularity'))
        appNm=appsSet.get_application(rqApp)['name']
        userAttributes = user_set.newUserItem(
            name=user_set.getNextUserId(),
            requestedApp=rqApp,  # Randomly select an application based on popularity
            appName=appNm,
            requestRatio=get_random_from_range(config, 'user', 'request_popularity'),
            connectedTo=selectRandomGraphNodeByCentrality(infrastructure, get_random_from_range(config, 'user', 'centrality')),  # Randomly select a node from the graph
            actions=user_actions_config
        )
        user_set.add_user(userAttributes)
    
    for user in user_set.get_all_users().values():
        generate_events(user, 'user', events_list)

    return user_set
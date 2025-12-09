import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
########################################

import random
import uuid

from utils import get_random_from_range, selectRandomAction

class ApplicationSet:
    def __init__(self):
        self.applications = {}
        # Initialize a counter to keep track of App IDs (App_0, App_1)
        self.app_counter = 0

    def getNextAppId(self):
        """Generates the next sequential application name."""
        name = f"App_{self.app_counter}"
        self.app_counter += 1
        return name

    def selectRandomAppByAggregatedPopularity(self, popularity):
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
        selected_app = random.choices(list(normalized_popularity.keys()), weights=normalized_popularity.values(), k=1)[0]
        return selected_app
    
    def selectRandomAppIdByPopularity(self, popularity):
        """Selects a random application based on its popularity."""
        selected_apps = [app for app in self.applications.values() if app['popularity'] >= popularity]
        if selected_apps:
            rndApp = random.choice(selected_apps)
            return rndApp['id']
        # If no applications meet the popularity criteria, return any random application to satisfy requirement of 
        # all the users should have an application to request  
        selected_apps = [app for app in self.applications.values()]
        rndApp = random.choice(selected_apps)
        return rndApp['id']

    def get_application_name_by_id(self, app_id):   
        """Retrieves the name of an application by its ID."""
        app = self.applications.get(app_id)
        if app:
            return app['name']
        return None
       
    def get_application_ram_by_name(self, app_name):
        """Retrieves the RAM requirement of an application by its name."""
        for app in self.applications.values():
            if app['name'] == app_name:
                return app['ram']
        return None

    def newAppItem(self, name, popularity, cpu, ram, disk, time, action):
        """Creates a new application item with the given attributes."""
        return {
            'name': name,
            'popularity': popularity,
            'cpu': cpu,
            'ram': ram,
            'disk': disk,
            'time': time,
            'action': action
        }

    def add_application(self, appAttributes):
        """Adds a new application to the set."""
        app_id = str(uuid.uuid4())  # Generates a unique identifier
        appAttributes['id'] = app_id
        self.applications[app_id] = appAttributes
        return app_id

    def remove_application(self, app_id, users):
        """Removes an application from the set based on its ID."""
        if app_id in self.applications:
            del self.applications[app_id]
            users.remove_user_by_requested_app(app_id)  # Remove users requesting this app
            return True
        return False

    def get_application(self, app_id):
        """Retrieves an application by its ID from the set."""
        return self.applications.get(app_id)

    def get_all_apps(self):
        """Returns all applications in the set."""
        return self.applications
    
    def __str__(self):
        """Returns a string representation of the ApplicationSet (the applications dictionary)."""
        return str(self.applications)
    
    def __repr__(self):
        """Official string representation for developers (useful for debugging)."""
        return f"ApplicationSet(applications={self.applications})"

def generate_random_apps(config):
    """
    Generates a list of random applications with random resource requirements.

    Args:
        num_apps (int): The number of applications to generate.
        **kwargs: Additional arguments to customize the application generation.

    Returns:
        list: A list of dictionaries representing the generated applications.
    """


    application_set = ApplicationSet()
    # Create some applications in the set

    attributes = config.get('attributes', {})
    app = attributes.get('app', {})
    num_apps = app.get('num_apps', 1)

    for i in range(num_apps):
       appAttributes=application_set.newAppItem(
            name=application_set.getNextAppId(),
            popularity=get_random_from_range(config, 'app', 'popularity'),  # Random popularity between 0.1 and 1.0
            cpu=get_random_from_range(config, 'app', 'cpu'),  # Random CPU requirement between 0.1 and 4.0 cores
            ram=get_random_from_range(config, 'app', 'ram'),  # Random RAM requirement between 0.5 and 8.0 GB
            disk=get_random_from_range(config, 'app', 'disk'),  # Random disk space requirement between 10 and 100 GB
            time = get_random_from_range(config, 'app', 'time'),
            action = selectRandomAction('app', config['attributes']['app']['action']) ) 
       application_set.add_application(appAttributes)
    return application_set

if __name__ == "__main__":
    print("appSet works fine")

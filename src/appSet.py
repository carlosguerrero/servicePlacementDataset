import random
import uuid

# BORRAr from utils import get_random_from_range, selectRandomAction
from .utils.auxiliar_functions import get_random_from_range, selectRandomAction
from .eventSet import EventSet, generate_events
from .userSet import create_new_user

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

    def newAppItem(self, name, popularity, cpu, ram, disk, time, actions):
        """Creates a new application item with the given attributes."""
        return {
            'name': name,
            'popularity': popularity,
            'cpu': cpu,
            'ram': ram,
            'disk': disk,
            'time': time,
            'actions': actions
        }

    def add_application(self, appAttributes):
        """Adds a new application to the set."""
        app_id = str(uuid.uuid4())  # Generates a unique identifier
        appAttributes['id'] = app_id
        self.applications[app_id] = appAttributes
        return app_id

    def remove_app(self, app_id, params):
        """Removes an application from the set based on its ID."""
        if params is None:
            params = {}
        users = params.get('user_set')
        event_set = params.get('event_set')

        if app_id in self.applications:
            del self.applications[app_id]
            print("DESDE appSet - remove_app:", app_id, "has been removed")
            users.remove_user_by_requested_app(app_id, params)  # Remove users requesting this app
            event_set.remove_events_by_object_id(app_id)

            message = f"Application {app_id} has been removed, along with its associated users and events."
            return message
        return False
    
    def increase_popularity(self, app_id, params):
        if params is None:
            params = {}
        multiplier = eval(params.get('multiplier'))
        old_popularity = self.applications[app_id]['popularity']

        self.applications[app_id]['popularity'] = self.applications[app_id]['popularity'] * multiplier

        users = params.get('user_set')
        users.increase_request_ratio_by_requested_app(app_id, params)

        message = f"Popularity of app {app_id} increased from {old_popularity} to {self.applications[app_id]['popularity']}"
        return message
    
    def decrease_popularity(self, app_id, params): 
        if params is None:
            params = {}
        multiplier = eval(params.get('multiplier'))
        old_popularity = self.applications[app_id]['popularity']

        self.applications[app_id]['popularity'] = self.applications[app_id]['popularity'] * multiplier

        users = params.get('user_set')
        users.decrease_request_ratio_by_requested_app(app_id, params)

        message = f"Popularity of app {app_id} decreased from {old_popularity} to {self.applications[app_id]['popularity']}"
        return message

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
    
    def new_app(self, app_id, params):
        """Creates a new user with random attributes based on the configuration."""
        config = params.get('config')
        app_set = params.get('app_set')
        infrastructure = params.get('infrastructure')
        user_set = params.get('user_set')
        event_set = params.get('event_set')
        num_new_users = eval(params.get('num_new_users'))

        # Se crea igual, no?
        # create_new_app(config, app_set, event_set)
        create_new_app(config, app_set, event_set)

        created_app_id = list(app_set.applications)[-1]

        for i in range(num_new_users):
            create_new_user(config, app_set, infrastructure, user_set, event_set, created_app_id)

        message = f"Application {created_app_id} has been created, along with {num_new_users} new users requesting this app."
        return message

def create_new_app(config, application_set, event_set):
    attributes = config.get('attributes', {})
    app_conf = attributes.get('app', {})
    app_actions_config =app_conf.get('actions', {})

    appAttributes=application_set.newAppItem(
            name=application_set.getNextAppId(),
            popularity=get_random_from_range(config, 'app', 'popularity'),  # Random popularity between 0.1 and 1.0
            cpu=get_random_from_range(config, 'app', 'cpu'),  # Random CPU requirement between 0.1 and 4.0 cores
            ram=get_random_from_range(config, 'app', 'ram'),  # Random RAM requirement between 0.5 and 8.0 GB
            disk=get_random_from_range(config, 'app', 'disk'),  # Random disk space requirement between 10 and 100 GB
            time=get_random_from_range(config, 'app', 'time'),
            actions=app_actions_config ) 
    
    application_set.add_application(appAttributes)
    generate_events(appAttributes, 'app', event_set)

def generate_random_apps(config, event_set):
    """
    Generates a list of random applications with random resource requirements.

    Args:
        num_apps (int): The number of applications to generate.
        **kwargs: Additional arguments to customize the application generation.

    Returns:
        list: A list of dictionaries representing the generated applications.
    """
    application_set = ApplicationSet()

    attributes = config.get('attributes', {})
    app_conf = attributes.get('app', {})
    num_apps = app_conf.get('num_apps', 1)

    for i in range(num_apps):
        create_new_app(config, application_set, event_set)
    return application_set

if __name__ == "__main__":
    print("appSet works fine")

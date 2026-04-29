import random
import uuid

from .utils.auxiliar_functions import get_random_from_range, selectRandomAction
from .eventSet import EventSet, generate_events
from .userSet import UserSet, create_new_user

# Note: I just added the DESCOMENTAR line to indicate where the event generation for the graph would be triggered

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
        selected_app = random_app.choices(list(normalized_popularity.keys()), weights=normalized_popularity.values(), k=1)[0]
        return selected_app
    
    def selectRandomAppIdByPopularity(self, popularity, sim_set):
        """Selects a random application based on its popularity."""
        selected_apps = [app for app in self.applications.values() if app['popularity'] >= popularity]
        
        rng = sim_set.rng_app
        
        if selected_apps:
            rndApp = rng.choice(selected_apps)
            return rndApp['id']

        selected_apps = [app for app in self.applications.values()]
        
        rndApp = rng.choice(selected_apps)
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
            message2 = users.remove_user_by_requested_app(app_id, params)  # Remove users requesting this app
            message = f"Application {self.applications[app_id]['name']} has been removed, along with its associated events. {message2}"
            del self.applications[app_id]
            event_set.remove_events_by_object_id(app_id)

            return message
        return False
    
    def increase_popularity(self, app_id, params):
        if params is None:
            params = {}

        sim_set = params.get('sim_set')
        multiplier = sim_set.parse_distribution(params.get('multiplier'), context='app')
        old_popularity = self.applications[app_id]['popularity']

        self.applications[app_id]['popularity'] = self.applications[app_id]['popularity'] * multiplier

        users = params.get('user_set')
        users.increase_request_ratio_by_requested_app(app_id, params)

        message = f"Popularity of app {self.applications[app_id]['name']} increased from {old_popularity} to {self.applications[app_id]['popularity']}"
        return message
    
    def decrease_popularity(self, app_id, params): 
        if params is None:
            params = {}

        sim_set = params.get('sim_set')
        multiplier = sim_set.parse_distribution(params.get('multiplier'), context='app')
        old_popularity = self.applications[app_id]['popularity']

        self.applications[app_id]['popularity'] = self.applications[app_id]['popularity'] * multiplier

        users = params.get('user_set')
        users.decrease_request_ratio_by_requested_app(app_id, params)

        message = f"Popularity of app {self.applications[app_id]['name']} decreased from {old_popularity} to {self.applications[app_id]['popularity']}"
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
        sim_set = params.get('sim_set')
        num_new_users = sim_set.parse_distribution(params.get('num_new_users'), context='app')

        create_new_app(config, app_set, event_set, sim_set)

        created_app_id = list(app_set.applications)[-1]

        for i in range(num_new_users):
            create_new_user(config, app_set, infrastructure, user_set, event_set, sim_set, created_app_id)

        message = f"Application {self.applications[created_app_id]['name']} has been created, along with {num_new_users} new users requesting this app."
        return message

def create_new_app(config, application_set, event_set, sim_set):
    attributes = config.get('attributes', {})
    app_conf = attributes.get('app', {})
    app_actions_config =app_conf.get('actions', {})

    appAttributes=application_set.newAppItem(
            name=application_set.getNextAppId(),
            popularity=sim_set.parse_distribution(app_conf.get('popularity'), context='app'), 
            cpu=sim_set.parse_distribution(app_conf.get('cpu'), context='app'),  
            ram=sim_set.parse_distribution(app_conf.get('ram'), context='app'), 
            disk=sim_set.parse_distribution(app_conf.get('disk'), context='app'),  
            time=sim_set.parse_distribution(app_conf.get('time'), context='app'),
            actions=app_actions_config ) 
    
    application_set.add_application(appAttributes)
    # DESCOMENTAR: generate_events(appAttributes, 'app', event_set, sim_set)

    return appAttributes['ram']

def generate_random_apps(config, event_set, sim_set, infrastructure, num_apps=None, saturation_percentage=None):
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
    
    attributes = config.get('attributes', {})
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
            print(f"Total RAM occupied after creating app {created_app_id}: {total_ram_occupied}%")

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

    return application_set, user_set

if __name__ == "__main__":
    print("appSet works fine")

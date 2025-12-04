# BORRAR: Here I will be running all the main code and calling the classeskept in other files
# BORRAR: from src.experimentSetup import experimentSetup

import yaml
import random
import uuid
import networkx as nx
from pulp import *

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def get_random_from_range(config, category, key, distribution=None):
    """Helper to get a random float between min and max defined in YAML.
    with the probability distribution function as we choose.
    """
    r = config['attributes'][category][key]
    dist_func = distribution if distribution else random.uniform
    return round(dist_func(r[0], r[1]), 2)

def _generate_random_graph(config):
    """Internal function to handle the 'random' generation mode."""
    setup = config.get('setup', {})
    model_params = config.get('model_params', {})
    
    model_name = setup.get('graph_model', 'erdos_renyi') # set to default if it's empty
    num_nodes = setup.get('num_nodes', 10)
    
    print(f"  [Random Mode] Generating {model_name} graph with {num_nodes} nodes...")
    
    # 1. Generate Topology
    if model_name == 'erdos_renyi':
        p = model_params.get('p', 0.1)
        graph = nx.erdos_renyi_graph(num_nodes, p)
    elif model_name == 'barabasi_albert':
        m = model_params.get('m', 2)
        if m >= num_nodes: m = 1
        graph = nx.barabasi_albert_graph(num_nodes, m)
    elif model_name == 'watts_strogatz':
        k = model_params.get('k', 4)
        p = model_params.get('p_rewire', 0.1)
        if k >= num_nodes: k = num_nodes - 1
        graph = nx.watts_strogatz_graph(num_nodes, k, p)
    elif model_name == 'balanced_tree':
        r = model_params.get('r', 2) 
        h = model_params.get('h', 3)
        graph = nx.balanced_tree(r, h)
    else:
        print(f"Graph model '{model_name}' not recognized.")
        return None

    # 2. Assign Random Attributes
    for node in graph.nodes():
        graph.nodes[node]['ram'] = get_random_from_range(config, 'node', 'ram')

    # 3. Assign Random Edge Delays
    for u, v in graph.edges():
        # BORRAR: graph.edges[u, v]['delay'] = round(random.uniform(0.1, 5.0), 2)
        graph.edges[u, v]['delay'] = get_random_from_range(config, 'edge', 'delay')
    return graph

# BORRAR: por ahora lo dejo estar
def _generate_manual_graph(config):
    """Internal function to handle the 'manual' generation mode."""
    print("  [Manual Mode] Building graph from defined topology...")
    graph = nx.Graph()
    
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

def generate_infrastructure(config):
    """
    Main entry point. Switches between manual and random generation
    based on the 'mode' setting in YAML.
    """
    setup = config.get('setup', {})
    mode = setup.get('mode', 'random')
    
    if mode == 'manual':
        graph = _generate_manual_graph(config)
    else:
        graph = _generate_random_graph(config)

    # --- Common Post-Processing ---
    # We calculate centrality for BOTH modes (unless you want to manually define it too)
    if graph and graph.number_of_nodes() > 0:
        try:
            betweenness_centrality = nx.betweenness_centrality(graph)
            for node, centrality in betweenness_centrality.items():
                graph.nodes[node]['betweenness_centrality'] = round(centrality, 4)
        except Exception as e:
            print(f"Could not calculate centrality: {e}")

    return graph

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

    def newUserItem(self, name, requestedApp, appName, requestRatio, connectedTo, time, action):
        """Creates a new user item with the given attributes."""
        return {
            'name': name,
            'requestedApp': requestedApp,
            'appName': appName,
            'requestRatio': requestRatio,
            'connectedTo': connectedTo,
            'time': time,
            'action': action
        }

    def getAllUsersByApp(self, appId):
        """Returns all users that requested a specific application."""
        return [user for user in self.users.values() if user['requestedApp'] == appId]
    
    def getAllUsersByNode(self, nodeId):
        """Returns all users connected to a specific node."""
        return [user for user in self.users.values() if user['connectedTo'] == nodeId]

    def add_user(self, userAttributes):
        """Adds a new user to the set."""
        user_id = str(uuid.uuid4())  # Generates a unique identifier
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
    
    def remove_user(self, user_id):
        """Removes a user from the set based on its ID."""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False
    
    # REVISAR: pendiente de definir
    def move_user(self, user_id, graph):
        node = None
        selected_nodes = [node for node, data in graph.nodes(data=True)] # if ]
        # quiero coger por ahora un nodo aleatprio que no esté cogido por ningún otro usuario
        # puede haber más de un usuario en el mismo nodo??
        # y que no sea el mismo que tenía hasta ahora

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

def generate_random_users(config, appsSet, infrastructure):
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
    app = attributes.get('user', {})
    num_users = app.get('num_users', 2)

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
            time = get_random_from_range(config, 'user', 'time'),
            action = selectRandomAction('user', config['attributes']['user']['action'])
        )
        user_set.add_user(userAttributes)
    return user_set

def selectRandomGraphNodeByCentrality(graph, centrality):  
    """
    Selects a random node from the graph based on its betweenness centrality.

    Args:
        graph (networkx.Graph): The input graph.
        centrality (float): The centrality threshold for selection.

    Returns:
        str: The ID of the selected node.
    """
    selected_nodes = [node for node, data in graph.nodes(data=True) if data['betweenness_centrality'] <= centrality]
    if selected_nodes:
        return random.choice(selected_nodes)
    return None

def selectRandomAction(type_object, probabilities):
    if type_object == 'user':
        actions = ["remove_user", "move_user"]
        return random.choices(actions, weights=probabilities, k=1)[0]
        # necesito asignarle una acción aleatoria de la lista:
        # remove_user o move_user
    elif type_object == 'app':
        # REVISAR
        actions = ["remove_app", "add_app"]
        return random.choices(actions, weights=probabilities, k=1)[0]
    else:
        return "No type_object recognized"

class EventSet:
    def __init__(self):
        self.events = {}
        self.global_time = 0

    def newUserItem(self, type_object, id, time, action):
        """Creates a new user item with the given attributes."""
        return {
            'type_object': type_object,
            'id': id,
            'time': time,
            'action': action
        }
    
    def add_event(self, eventAttributes):
        """Adds a new user to the set."""
        event_id = str(uuid.uuid4())  # Generates a unique identifier
        eventAttributes['id'] = event_id
        self.events[event_id] = eventAttributes
        return event_id

    def __str__(self):
        """Returns a string representation of the EventSet (the events list)."""
        return str(self.events)

def generate_events(objects_list, type_object, event_set):
    """type_object: 'user' or 'app'
    Later will be also be node"""

    for i in eval('objects_list' + '.get_all_' + type_object + 's().values()'):
        eventAttributes = event_set.newUserItem(
            id=i['id'],
            type_object=type_object,
            time = i['time'],
            action = i['action']
        )
        event_set.add_event(eventAttributes)
    return event_set

def solve_application_placement(graph, application_set, user_set):
    """Solves the application placement problem using ILP."""
    applications = application_set.get_all_apps()
    nodes = list(graph.nodes())
    users = user_set.get_all_users()

    # Pre-calculate all-pairs shortest paths based on 'delay'
    # This is crucial for efficient latency calculation in the objective function
    try:
        # Check if the graph is connected. If not, shortest_path_length might fail for some pairs.
        # For disconnected graphs, consider infinite delay or a large penalty.
        # Here, we assume connectivity for all relevant pairs.
        all_pairs_shortest_paths = dict(nx.all_pairs_dijkstra_path_length(graph, weight='delay'))
    except nx.NetworkXNoPath:
        print("Warning: Graph is disconnected. Some shortest paths might not exist.")
        # Handle disconnected components if necessary, e.g., by assigning a very large delay
        all_pairs_shortest_paths = {} # Fallback

    print(all_pairs_shortest_paths)

    # Decision variable: Is application 'a' placed on node 'n'? (Binary: 0 = no, 1 = yes)
    x_an = LpVariable.dicts("Place", [(app_id, node) for app_id in applications for node in nodes], cat='Binary')

    # Objective function: Minimize the total weighted latency
    prob = LpProblem("Application_Placement", LpMinimize)

    # The objective is built directly using the pre-calculated shortest paths
    objective_terms = []
    for user_id, user_data in users.items():
        requested_app_id = user_data['requestedApp']
        user_home_node = user_data['connectedTo']

        if requested_app_id and user_home_node is not None:
            # Sum over all possible placement nodes for the requested app
            # Only one x_an for a given requested_app_id will be 1
            for node_app_placed in nodes:
                # Get the delay from the user's home node to the node where the app is placed
                delay_value = all_pairs_shortest_paths.get(user_home_node, {}).get(node_app_placed, float('inf'))
                # Add term: (delay * request_ratio * x_an)
                objective_terms.append(delay_value * user_data['requestRatio'] * x_an[requested_app_id, node_app_placed])
        
    prob += lpSum(objective_terms), "Total Weighted Latency"

    # Constraint 1: Each application is placed on exactly one node
    for app_id in applications:
        prob += lpSum(x_an[app_id, node] for node in nodes) == 1, f"PlacementConstraint_{app_id}"

    # Constraint 2: Total RAM used on a node does not exceed its capacity
    for node in nodes:
        prob += lpSum(applications[app_id]['ram'] * x_an[app_id, node] for app_id in applications) <= graph.nodes[node]['ram'], f"RAMConstraint_{node}"

    # Solve the ILP problem
    prob.solve(PULP_CBC_CMD(msg=0)) # msg=0 to suppress solver output

    if LpStatus[prob.status] == "Optimal":
        print("\nOptimal Application Placement Found:")
        placement = {}
        total_ram_used_per_node = {node: 0.0 for node in nodes}
        for app_id, app_data in applications.items():
            for node in nodes:
                if value(x_an[app_id, node]) == 1:
                    placement[app_data['name']] = node
                    total_ram_used_per_node[node] += app_data['ram']
                    break

        # Update the graph nodes with the placement information
        #for node in nodes:
        #    graph.nodes[node]['running_applications'] = [] # Reset before updating
        #    graph.nodes[node]['ram_used'] = 0.0 # Reset before updating

        #for app_id, app_data in applications.items():
        #    for node in nodes:
        #        if value(x_an[app_id, node]) == 1:
        #            graph.nodes[node]['running_applications'].append(app_id)
        #            graph.nodes[node]['ram_used'] += app_data['ram'] # Already accumulated in total_ram_used_per_node, but update node attribute

        return placement, value(prob.objective)
    else:
        print(f"No Optimal Solution Found. Status: {LpStatus[prob.status]}")
        return None, None

# REVISAR: CARLOS no sé si esta es la forma más óptima de hacerlo
def update_system_state(event, update_set):
    if event[1]['action'].startswith('remove'):
        # No need to update anything
        print("Id es ", event[1]['id'])
        update_set = update_set.remove_user(event[1]['id']) 
        # update_set = eval('update_set.' + event[1]['action'] + '(' + event[1]['id'] + ')')
        # BORRAR: update_set = eval(f"update_set.{event[1]['action']}({repr(event[1]['id'])})")

        return update_set
    elif event[1]['action'].startswith('move'):
        # user_set.move_user(event[1]['id'])) # por graph
        # Hay que actualizar el nodo al que está conectado el usuario
        # y también hay que asignar un nuevo tiempo: random time + global_time
        pass

def scenario1(events_list, application_set, user_set):
    sorted_events = sorted(events_list.items(), key=lambda item: item[1]['time'])
    global_time = 0
    while sorted_events or global_time < 300:
        for event in sorted_events:
            global_time = event[1]['time']
            if event[1]['type_object'] == 'user':
                user_set = update_system_state(event, user_set)
            elif event[1]['type_object'] == 'app':
                application_set = update_system_state(event, application_set)
            
            print(f"Global Time: {global_time}")
            print(f"Users: {user_set}")

    return sorted_events

def main():
    random.seed(42)

    # MANUAL GENERATION OF GRAPH: config_manual = "config_manual.yaml"

    config_random = "config_random.yaml"
    config = load_config(config_random)

    # RANDOM GENERATION OF GRAPH
    generated_infrastructure = generate_infrastructure(config)
    print(f"Nodes: {generated_infrastructure.number_of_nodes()}")
    print(f"Edges: {generated_infrastructure.number_of_edges()}")
    first_edge = list(generated_infrastructure.edges())[0]
    print(f"Edge {first_edge} Attributes: {generated_infrastructure.edges[first_edge]}")
    
    generated_apps = generate_random_apps(config)
    print(f"Apps: {generated_apps}")

    generated_users = generate_random_users(config, generated_apps, generated_infrastructure)
    print(f"Users: {generated_users}")

    # SOLVE PROBLEM
    if generated_apps and generated_users and generated_infrastructure:
        optimal_placement, total_latency = solve_application_placement(generated_infrastructure, generated_apps, generated_users)

        if optimal_placement:
            print("Application Placement:", optimal_placement)
            print("Total Latency:", total_latency)
            print("\nUpdated Node Information with Application Placement:")
            for node in generated_infrastructure.nodes(data=True):
                print(f"Node {node[0]}: RAM Total={node[1].get('ram')}, RAM Used={node[1].get('ram_used')}, Running Apps={[generated_apps.get_application(app_id)['name'] for app_id in node[1].get('running_applications', [])]}")
            # return optimal_placement
        else:
            print("No feasible solution found for application placement.")

    

    # WORKING ON ITERATIONS
    print(" ")
    print("---- EVENTS ----")

    

    generated_events = EventSet()
    generated_events = generate_events(generated_users, 'user', generated_events)
    # REVISAR: Por ahora no añado las apps aún
    # generated_events = generate_events(generated_apps, 'app', generated_events)
    print(generated_events)

    # print("Elemento eliminado: ", list(generated_users.get_all_users().keys())[0])
    # generated_users.remove_user(list(generated_users.get_all_users().keys())[0])  # Remove first user for testing

    scenario1(generated_events.events, generated_apps, generated_users)


if __name__ == "__main__":
    main()

            

import networkx as nx
import random
import uuid
from pulp import *
random.seed(40)  # Fija la semilla para que los resultados sean reproducibles

class experimentSetup:
    def __init__(self):
        self.appId=0
        self.userId=0
        self.nodeId=0
    
    def getNextAppId(self):
        currentId = self.appId
        self.appId += 1
        return currentId
    def getNextUserId(self):
        currentId = self.userId
        self.userId += 1
        return currentId
    def getNextNodeId(self):    
        currentId = self.nodeId
        self.nodeId += 1
        return currentId

    def num_nodes(self):
        return 10 # Default number of nodes if not specified
    def num_apps(self):
        return 1 # Default number of applications if not specified
    def num_users(self):
        return 2 # Default number of users if not specified
    def graph_model(self):
        return 'erdos_renyi' # Default graph model if not specified
        #return 'balanced_tree'

    #NODE ATTRIBUTES
    def node_ram(self):
        return round(random.uniform(1.0, 16.0), 2)  # Random RAM

    #APP ATTRIBUTES
    def popularity(self):
        return round(random.uniform(0.1, 1.0), 2)  # Random popularity 
    def cpu(self):
        return round(random.uniform(0.1, 4.0), 2) # Random CPU
    def app_ram(self):
        return round(random.uniform(0.5, 8.0), 2) # Random RAM
    def disk(self):
        return round(random.uniform(10, 100), 2) # Random disk space
    
    #USER ATTRIBUTES
    def request_ratio(self):    
        return round(random.uniform(0.1, 1.0), 2)
    def request_popularity(self):
        return round(random.uniform(0.1, 1.0), 2)
    def centrality(self):
        return round(random.uniform(0.1, 1.0), 2)

    def __str__(self):
        return f"Experiment Setup: {self.num_nodes} nodes, {self.num_apps} applications, {self.num_users} users, Graph Model: {self.graph_model}"

class UserSet:
    def __init__(self):
        self.users = {}

    def newUserItem(self, name, requestedApp, appName, requestRatio, connectedTo):
        """Creates a new user item with the given attributes."""
        return {
            'name': name,
            'requestedApp': requestedApp,
            'appName': appName,
            'requestRatio': requestRatio,
            'connectedTo': connectedTo
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


class ApplicationSet:
    def __init__(self):
        self.applications = {}

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

    def newAppItem(self, name, popularity, cpu, ram, disk):
        """Creates a new application item with the given attributes."""
        return {
            'name': name,
            'popularity': popularity,
            'cpu': cpu,
            'ram': ram,
            'disk': disk
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

    def get_all_applications(self):
        """Returns all applications in the set."""
        return self.applications
    def __str__(self):
        """Returns a string representation of the ApplicationSet (the applications dictionary)."""
        return str(self.applications)
    
    def __repr__(self):
        """Official string representation for developers (useful for debugging)."""
        return f"ApplicationSet(applications={self.applications})"

def generate_random_apps(setup, **kwargs):
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
    for i in range(setup.num_apps()):
       appAttributes=application_set.newAppItem(
            name=f"App_{setup.getNextAppId()}",
            popularity=setup.popularity(),  # Random popularity between 0.1 and 1.0
            cpu=setup.cpu(),  # Random CPU requirement between 0.1 and 4.0 cores
            ram=setup.app_ram(),  # Random RAM requirement between 0.5 and 8.0 GB
            disk=setup.disk()  ) # Random disk space requirement between 10 and 100 GB
       application_set.add_application(appAttributes)
    return application_set

def generate_random_users(setup, appsSet, infrastructure, **kwargs):
    """
    Generates a list of random users with random application requests.

    Args:
        num_users (int): The number of users to generate.
        **kwargs: Additional arguments to customize the user generation.

    Returns:
        list: A list of dictionaries representing the generated users.
    """
    user_set = UserSet()
    # Create some users in the set
    for i in range(setup.num_users()):
        rqApp=appsSet.selectRandomAppIdByPopularity(setup.request_popularity())
        print(rqApp)
        appNm=appsSet.get_application(rqApp)['name']
        print(appNm)
        userAttributes = user_set.newUserItem(
            name=f"User_{setup.getNextUserId()}",
            requestedApp=rqApp,  # Randomly select an application based on popularity
            appName=appNm,
            requestRatio=setup.request_ratio(),
            connectedTo=selectRandomGraphNodeByCentrality(infrastructure, setup.centrality())  # Randomly select a node from the graph
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



def generate_random_infrastructure(setup, **kwargs):
    """
    Generates a random graph using the NetworkX library.

    Args:
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
    if setup.graph_model() == 'erdos_renyi':
        probability = kwargs.get('p', 0.1)  # Default probability of 0.1 if not specified
        graph = nx.erdos_renyi_graph(setup.num_nodes(), probability)
    elif setup.graph_model() == 'barabasi_albert':
        edges_per_new_node = kwargs.get('m', 2)  # Default number of edges to attach if not specified
        graph = nx.barabasi_albert_graph(setup.num_nodes(), edges_per_new_node)
    elif setup.graph_model() == 'watts_strogatz':
        initial_neighbors = kwargs.get('k', 4)  # Default initial number of neighbors
        rewiring_probability = kwargs.get('p_rewire', 0.1)  # Default rewiring probability
        graph = nx.watts_strogatz_graph(setup.num_nodes(), initial_neighbors, rewiring_probability)
    elif setup.graph_model() == 'balanced_tree':
        branching_factor = 2  # Default initial number of neighbors
        height = 2  # Default rewiring probability
        graph = nx.balanced_tree(branching_factor, height)
 
    else:
        print(f"Graph model '{setup.graph_model()}' not recognized.")
        return None

    # Assign random 'ram' attributes to each node
    for node in graph.nodes():
        graph.nodes[node]['ram'] = setup.node_ram()  # Assign the same random RAM size to all nodes


    # Calculate betweenness centrality
    betweenness_centrality = nx.betweenness_centrality(graph)

    # Assign betweenness centrality as a node attribute
    for node, centrality in betweenness_centrality.items():
        graph.nodes[node]['betweenness_centrality'] = centrality

    # Assign a random 'delay' attribute to each edge
    for u, v in graph.edges():
        graph.edges[u, v]['delay'] = round(random.uniform(0.1, 5.0), 2) # Delay in milliseconds

    return graph

def solve_application_placement(graph, application_set, user_set):
    """Solves the application placement problem using ILP."""
    applications = application_set.get_all_applications()
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

    # Decision variable: Is application 'a' placed on node 'n'? (Binary)
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
        print("Application Placement:", placement)
        print("Total Weighted Latency:", value(prob.objective))

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


def solve_application_placementOLD(graph, application_set, user_set):
    """Solves the application placement problem using ILP."""
    applications = application_set.get_all_applications()
    nodes = list(graph.nodes())
    users = user_set.get_all_users()

    # Decision variable: Is application 'a' placed on node 'n'? (Binary)
    x_an = LpVariable.dicts("Place", [(app_id, node) for app_id in applications for node in nodes], cat='Binary')

    # Decision variable: Latency between user 'u' and application 'a'
    latency_ua = LpVariable.dicts("Latency", [(user_id, app_id) for user_id in users for app_id in applications], lowBound=0)

    # Objective function: Minimize the weighted average latency
    objective = lpSum([latency_ua[user_id, app_id] * users[user_id]['requestRatio']
                      for user_id in users for app_id in applications if users[user_id]['requestedApp'] == app_id])

    prob = LpProblem("Application Placement", LpMinimize)
    prob += objective, "Total Weighted Latency"

    # Constraint 1: Each application is placed on exactly one node
    for app_id in applications:
        prob += lpSum(x_an[app_id, node] for node in nodes) == 1, f"PlacementConstraint_{app_id}"

    # Constraint 2: Total RAM used on a node does not exceed its capacity
    for node in nodes:
        prob += lpSum(applications[app_id]['ram'] * x_an[app_id, node] for app_id in applications) <= graph.nodes[node]['ram'], f"RAMConstraint_{node}"

    # Constraint 3: Define latency_ua based on the placement
    for user_id in users:
        requested_app_id = users[user_id]['requestedApp']
        if requested_app_id:
            for node in nodes:
                # If application is placed on the node, latency is the shortest path
                shortest_path = nx.shortest_path_length(graph, source=int(list(users.keys()).index(user_id)), target=node, weight='delay')
                prob += latency_ua[user_id, requested_app_id] >= shortest_path * x_an[requested_app_id, node], f"LatencyDef_{user_id}_{requested_app_id}_{node}"
                # If application is not placed, latency can be large (or handled differently based on problem definition)
                # Here, we ensure latency is at least 0, which is already defined in the variable bounds.

    # Solve the ILP problem
    prob.solve()

    if LpStatus[prob.status] == "Optimal":
        print("\nOptimal Application Placement Found:")
        placement = {}
        for app_id in applications:
            for node in nodes:
                if value(x_an[app_id, node]) == 1:
                    placement[applications[app_id]['name']] = node
                    break
        print("Application Placement:", placement)
        print("Total Weighted Latency:", value(prob.objective))

        # # Update the graph nodes with the placement information
        # for app_name, node_index in placement.items():
        #     for app_id, app_data in applications.items():
        #         if app_data['name'] == app_name:
        #             graph.nodes[node_index]['running_applications'].append(app_id)
        #             graph.nodes[node_index]['ram_used'] += app_data['ram_required']
        #             break
        return placement, value(prob.objective)
    else:
        print("No Optimal Solution Found.")
        return None, None


if __name__ == "__main__":

    setup = experimentSetup()


    users_parameters = {}
    apps_parameters = {}
    parameters = {}
    if setup.graph_model() == 'erdos_renyi':
        edge_probability = 0.2 #Enter the probability of creating an edge (between 0 and 1)
        parameters['p'] = edge_probability
    elif setup.graph_model() == 'barabasi_albert':
        m_value = 2 #Enter the number of edges to attach per each new node
        parameters['m'] = m_value
    elif setup.graph_model() == 'watts_strogatz':
        k_value = 2 #Enter the initial number of neighbors for each node
        parameters['k'] = k_value
        p_rewire_value = 0.1 #Enter the rewiring probability (between 0 and 1)
        parameters['p_rewire'] = p_rewire_value

    generated_infrastructure = generate_random_infrastructure(setup, **parameters)
    generated_apps = generate_random_apps(setup, **apps_parameters)
    generated_users = generate_random_users(setup, generated_apps, generated_infrastructure, **users_parameters)

    if generated_infrastructure:
        print(f"\nGraph generated with {generated_infrastructure.number_of_nodes()} nodes and {generated_infrastructure.number_of_edges()} edges, using the '{setup.graph_model()}' model.")

        for node in generated_infrastructure.nodes():
            print(generated_infrastructure.nodes[node])

    if generated_apps:
        print(generated_apps)

    if generated_users:
        print(generated_users)

    if generated_apps and generated_users and generated_infrastructure:

        optimal_placement, total_latency = solve_application_placement(generated_infrastructure, generated_apps, generated_users)

        if optimal_placement:
            print("Application Placement:", optimal_placement)
            print("Total Latency:", total_latency)
            print("\nUpdated Node Information with Application Placement:")
            for node in generated_infrastructure.nodes(data=True):
                print(f"Node {node[0]}: RAM Total={node[1].get('ram')}, RAM Used={node[1].get('ram_used')}, Running Apps={[generated_apps.get_application(app_id)['name'] for app_id in node[1].get('running_applications', [])]}")
        else:
            print("No feasible solution found for application placement.")

    if generated_infrastructure:
        # Optional: You can perform more operations with the graph here, such as visualizing it
        import matplotlib.pyplot as plt
        #pos = nx.spring_layout(generated_infrastructure)
        pos = nx.spring_layout(generated_infrastructure, k=0.3, iterations=500) # Ajustar k e iterations
        #pos = nx.spring_layout(generated_infrastructure, k=10.0, iterations=50) # Ajustar k e iterations


        # Labels of the nodes with their attributes
        node_labels = {
            node: f"ID:{node}\nR:{data.get('ram', 'N/A')}\nUs:{[generated_apps.get_application_name_by_id(userElement['requestedApp']).split("_")[-1]+"("+str(userElement['requestRatio'])+")" for userElement in generated_users.getAllUsersByNode(node)]}\nAp:{[placedAppName.split("_")[-1]+"("+str(generated_apps.get_application_ram_by_name(placedAppName))+")" for placedAppName, placedNode in optimal_placement.items() if placedNode == node]}"
            for node, data in generated_infrastructure.nodes(data=True)
        }

        # Lables of the edges with the attribute delay
        edge_labels = {(u, v): f"{data.get('delay', 'N/A')}t" for u, v, data in generated_infrastructure.edges(data=True)}

        # Draw the nodes
        nx.draw_networkx_nodes(generated_infrastructure, pos, node_size=1500, node_color='lightblue')


        # Draw node labels with adjusted font size and alignment of the nodes
        nx.draw_networkx_labels(generated_infrastructure, pos, labels=node_labels, font_size=5, verticalalignment='center_baseline')

        # Draw the edges
        nx.draw_networkx_edges(generated_infrastructure, pos, alpha=0.5)

        # Draw edge labels with adjusted font size
        nx.draw_networkx_edge_labels(generated_infrastructure, pos, edge_labels=edge_labels, font_size=6)

        plt.title("Graph with Node and Edge Attributes")
        plt.show()
        #nx.draw(generated_infrastructure, with_labels=True, node_color='lightblue', node_size=500, font_size=10, font_weight='bold')
        #plt.title(f"{setup.graph_model()} Graph")
        #plt.show()



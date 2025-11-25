import random

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
        return f"Experiment Setup: {self.num_nodes()} nodes, {self.num_apps()} applications, {self.num_users()} users, Graph Model: {self.graph_model()}"
        # BORRAR: return f"Experiment Setup: {self.num_nodes} nodes, {self.num_apps} applications, {self.num_users} users, Graph Model: {self.graph_model}"


# RUN SOME TESTS 
if __name__ == "__main__":

    setup = experimentSetup()
    print("Setup: ", setup)

    # Test ID generation
    print("App IDs:", [setup.getNextAppId() for _ in range(4)])
    print("User IDs:", [setup.getNextUserId() for _ in range(3)])
    print("Node IDs:", [setup.getNextNodeId() for _ in range(3)])

    # Test random attributes
    print("Node RAM:", setup.node_ram())
    print("App CPU:", setup.cpu())
    print("App RAM:", setup.app_ram())
    print("Disk:", setup.disk())
    print("User Centrality:", setup.centrality())

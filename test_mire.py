
# CODE FOR READING pkl files
# with open('simulation_results.pkl', 'rb') as f:  # 'rb' means Read Binary
# loaded_results = pickle.load(f)

# Now you have your actual objects back!
# first_result = loaded_results[0]
# print(first_result.total_latency) # Works perfectly

import yaml
import random
import uuid
import networkx as nx
from pulp import *
import pickle

from src import EventSet, generate_events, ApplicationSet, generate_random_apps, UserSet, generate_random_users
from main import generate_infrastructure, load_config

if __name__ == "__main__":
    random.seed(42)

    config_random = "config_random.yaml"
    config = load_config(config_random)

    # RANDOM GENERATION OF GRAPH
    generated_infrastructure = generate_infrastructure(config)
    print(f"Nodes: {generated_infrastructure.number_of_nodes()}")
    print(f"Edges: {generated_infrastructure.number_of_edges()}")

    generated_apps = generate_random_apps(config)
    print(f"Apps: {generated_apps}")

    generated_users = generate_random_users(config, generated_apps, generated_infrastructure)
    print(f"Users: {generated_users}")


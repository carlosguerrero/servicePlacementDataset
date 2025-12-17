
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
import copy

from src import EventSet, generate_events, ApplicationSet, generate_random_apps, UserSet, generate_random_users
from main import generate_infrastructure, load_config


def get_neighbors_centrality(graph, centrality, node_id):
    """
    Retorna un diccionario de los nodos adyacentes a 'node_id' 
    y su valor de 'betweenness_centrality'.
    """
    adjacent_nodes = graph.neighbors(node_id)
    adjacent_nodes_info = {
        n: graph.nodes[n].get('betweenness_centrality', 0) 
        for n in adjacent_nodes
    }

    adjacent_nodes_info_filtered = {node: btw_c for node, btw_c in adjacent_nodes_info.items() if btw_c <= centrality}

    if not adjacent_nodes_info_filtered:
        return None
    
    # We want to choose the node randomly but with weights favoring the lowest betweenness centrality
    nodes = list(adjacent_nodes_info_filtered.keys())
    centralities = list(adjacent_nodes_info_filtered.values())

    epsilon = 0.0001
    max_c = max(centralities) + epsilon
    weights = [max_c - c for c in centralities]
    selection = random.choices(nodes, weights=weights, k=1)

    return adjacent_nodes_info_filtered

def select_node_low_centrality(neighbors_dict):
    if not neighbors_dict:
        return None

    nodes = list(neighbors_dict.keys())
    centralities = list(neighbors_dict.values())

    # 1. Invertir los pesos: a menor centralidad, mayor peso.
    # Sumamos un pequeño valor (epsilon) para evitar problemas si la centralidad es 0.
    epsilon = 0.0001
    max_c = max(centralities) + epsilon
    
    # Peso = Centralidad Máxima detectada - Centralidad del nodo
    # Así, el que tiene centralidad 0 obtiene el peso más alto.
    weights = [max_c - c for c in centralities]

    # 2. Selección aleatoria ponderada
    # k=1 significa que solo queremos un elemento
    selection = random.choices(nodes, weights=weights, k=1)
    
    return selection[0]

if __name__ == "__main__":
    random.seed(42)

    config_random = "config_random.yaml"
    config = load_config(config_random)

    # RANDOM GENERATION OF GRAPH
    generated_infrastructure = generate_infrastructure(config)
    print(f"Nodes: {generated_infrastructure.number_of_nodes()}")
    print(f"Edges: {generated_infrastructure.number_of_edges()}")

    generated_events = EventSet()

    generated_apps = generate_random_apps(config)
    print(f"Apps: {generated_apps}")

    generated_users = generate_random_users(config, generated_apps, generated_infrastructure, generated_events)
    print(f"\nUsers: {generated_users}")
    print("\nEvents in the set:", generated_events)

    print("\nPRUEBAS")
    print("NODES:", generated_infrastructure.nodes(data=True))
    print("EDGES:", generated_infrastructure.edges(data=True))

    node_id = 1
    centrality = 5

    neighbors_centrality = get_neighbors_centrality(generated_infrastructure, centrality, node_id)
    print(" ")
    print(neighbors_centrality)




    


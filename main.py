import yaml
import os
from src.simulationSet import SimulationSet
from src.simulation_runner import ServicePlacementSimulation

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def run_simulation(config_path: str = "config_random.yaml", master_seed: int = 42, total_iterations: int = 500) -> None:
    # Keep entrypoint compatible, but delegate orchestration to the new runner.
    sim_set = SimulationSet(master_seed=master_seed)

    full_config_path = config_path
    if not os.path.isabs(full_config_path):
        full_config_path = os.path.join(os.path.dirname(__file__), full_config_path)
    config = load_config(full_config_path)

    ServicePlacementSimulation(
        config=config,
        sim_set=sim_set,
        total_iterations=total_iterations,
    ).run()


def main():
    run_simulation()


if __name__ == "__main__":
    main()
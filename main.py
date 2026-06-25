import yaml
import os
import logging
from src.simulationSet import SimulationSet
from src.simulation_runner import ServicePlacementSimulation
from src.constants import DEFAULT_CONFIG_FILE, DEFAULT_MASTER_SEED, DEFAULT_TOTAL_ITERATIONS

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def run_simulation(config_path: str = DEFAULT_CONFIG_FILE, master_seed: int = DEFAULT_MASTER_SEED, total_iterations: int = DEFAULT_TOTAL_ITERATIONS) -> None:
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


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )

def main():
    setup_logging()
    run_simulation()


if __name__ == "__main__":
    main()
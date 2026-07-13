import yaml
import os
import argparse
import logging
from src.simulationSet import SimulationSet
from src.simulation_runner import ServicePlacementSimulation
from src.constants import (
    DEFAULT_SCENARIO_CONFIG_FILE,
    DEFAULT_SOLVER_CONFIG_FILE,
    DEFAULT_MASTER_SEED,
    DEFAULT_TOTAL_ITERATIONS,
)

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def run_simulation(
    scenario_path: str = DEFAULT_SCENARIO_CONFIG_FILE,
    solver_path: str = DEFAULT_SOLVER_CONFIG_FILE,
    master_seed: int = DEFAULT_MASTER_SEED,
    total_iterations: int = DEFAULT_TOTAL_ITERATIONS,
) -> None:
    full_scenario_path = scenario_path if os.path.isabs(scenario_path) else os.path.join(os.path.dirname(__file__), scenario_path)
    full_solver_path = solver_path if os.path.isabs(solver_path) else os.path.join(os.path.dirname(__file__), solver_path)
    scenario_config = load_config(full_scenario_path) or {}
    solver_config = load_config(full_solver_path) or {}
    config = {**scenario_config, **solver_config}
    config["_scenario_config_path"] = full_scenario_path
    config["_solver_config_path"] = full_solver_path

    sim_set = SimulationSet.from_config(config, default_master_seed=master_seed)

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
    parser = argparse.ArgumentParser(description="ECCOS Service Placement Simulator")
    parser.add_argument("--scenario", "-s", type=str, default=DEFAULT_SCENARIO_CONFIG_FILE, help="Path to scenario config YAML")
    parser.add_argument("--solver", "-c", type=str, default=DEFAULT_SOLVER_CONFIG_FILE, help="Path to solver config YAML")
    parser.add_argument("--seed", type=int, default=DEFAULT_MASTER_SEED, help="Master random seed")
    parser.add_argument("--iterations", "-i", type=int, default=DEFAULT_TOTAL_ITERATIONS, help="Total simulation iterations")
    args = parser.parse_args()

    run_simulation(
        scenario_path=args.scenario,
        solver_path=args.solver,
        master_seed=args.seed,
        total_iterations=args.iterations,
    )


if __name__ == "__main__":
    main()
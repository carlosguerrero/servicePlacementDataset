# GAIM — Service Placement Simulator for the Computing Continuum

GAIM is an event-driven simulator written in Python for studying the dynamic placement of applications in Computing Continuum (CC) environments — traditionally known as Fog or Edge Computing. It generates a synthetic infrastructure, populates it with applications and users whose behaviour evolves over time, and at every simulation step solves an Integer Linear Program (ILP) that decides on which node each application should run so that total user-weighted latency is minimized under RAM capacity constraints.

The simulator is fully YAML-driven and fully seeded: every stochastic decision is derived from one of four domain-specific random generators, which makes experiments reproducible across machines and operating systems.

---

## Table of contents

- [Features](#features)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running a simulation](#running-a-simulation)
- [Configuration (`config_random.yaml`)](#configuration-config_randomyaml)
- [Outputs](#outputs)
- [Visualization](#visualization)
- [Reproducibility](#reproducibility)
- [Extending the simulator](#extending-the-simulator)

---

## Features

- **Scale-free infrastructure** — Barabási–Albert topology by default, with optional Erdős–Rényi, Watts–Strogatz, and balanced-tree models.
- **Heterogeneous, degree-correlated resources** — RAM drawn from a Pareto distribution and assigned in decreasing order of node degree, so well-connected hubs get the most memory (80/20 pattern).
- **Stochastic dynamics** — users arrive, leave, move, and change their request ratio; applications gain and lose popularity; nodes and edges fail and recover. Every event type has its own tunable distribution.
- **ILP-based service placement** — at every iteration, PuLP + CBC solves a binary ILP that minimizes total weighted latency subject to per-node RAM capacity.
- **Shortest-path caching** — all-pairs Dijkstra paths are cached on the infrastructure object and recomputed only when the topology changes.
- **YAML-driven configuration** — all distributions, counts and saturation targets are declared in a single YAML file, not hardcoded in Python.
- **Reproducibility by design** — four independent `numpy.random.Generator` instances (one per simulation domain) are seeded from a single master seed.
- **Rich logging** — per-iteration JSON snapshots, per-iteration GML graphs, and a CSV log of user counts.

---

## Project structure

```
.
├── main.py                  # Simulation entry point and ILP solver
├── config_random.yaml       # Random-graph configuration (default)
├── config_manual.yaml       # Manually-defined topology (optional)
├── visual_results.py        # Plots from the CSV log
├── pyproject.toml
├── .python-version
└── src/
    ├── __init__.py
    ├── simulationSet.py     # Master-seeded, per-domain RNGs + YAML distribution parser
    ├── eventSet.py          # Global event list + event scheduling
    ├── infrastructure.py    # Graph generation + node/edge events
    ├── appSet.py            # Application generation + app events
    ├── userSet.py           # User generation + user events
    ├── simulation.py        # Output folder, JSON/GML/CSV logging, stop conditions
    └── utils/
        ├── __init__.py
        └── auxiliar_functions.py   # Centrality-aware node selection, mobility
```

## Requirements

- Python 3.12 or later
- `numpy`
- `networkx`
- `pulp` (which pulls in the CBC solver)
- `pyyaml`
- `pandas` and `matplotlib` (only needed for `visual_results.py`)

## Installation

Clone the repository, create a virtual environment, and install the dependencies:

```bash
git clone <repository-url>
cd servicePlacementDataset

python3.12 -m venv .venv
source .venv/bin/activate         # On Windows: .venv\Scripts\activate

pip install numpy networkx pulp pyyaml pandas matplotlib
```

If you prefer `uv` (the project ships a `.python-version` file for it):

```bash
uv venv
uv pip install numpy networkx pulp pyyaml pandas matplotlib
```

## Running a simulation

From the project root:

```bash
python main.py
```

The entry point performs the following steps, each of which is logged to stdout:

1. Create a `SimulationSet` with master seed `42`.
2. Load `config_random.yaml`.
3. Generate the infrastructure (graph, RAM per node, delay per edge, betweenness centrality).
4. Create applications up to the configured saturation percentage and, for each, one or more users tied to it.
5. Schedule the initial recurring `new_user` event (Little's Law arrival process).
6. Solve the ILP once to produce the initial placement.
7. Run the event loop for up to 500 iterations, solving the ILP after every event.

A new timestamped folder is created under `Simulations_raw/` for each run, e.g. `Simulations_raw/Sim_20260422_103045/`.

## Configuration (`config_random.yaml`)

The YAML file is organized in three top-level blocks:

- **`setup`** — generation mode (`random` or `manual`), number of nodes, and graph model.
- **`model_params`** — parameters specific to the chosen graph model (`m` for Barabási–Albert, `p_rewire`/`k` for Watts–Strogatz, etc.).
- **`attributes`** — per-domain attributes and actions for the `graph`, `app`, `user`, and `new_object` domains. Each action declares its firing distribution and, optionally, its multipliers.

Distributions are written as strings that will be evaluated through the domain RNG, e.g.:

```yaml
user:
  request_ratio: 'rng.exponential(5)'
  actions:
    move_user:
      distribution: 'rng.exponential(120)'
    increase_request_ratio:
      distribution: 'rng.exponential(90)'
      action_params:
        multiplier: 'rng.uniform(1, 3)'
```

The parser accepts any expression of the form `rng.<numpy_method>(...)` (or `np.<...>(...)`), evaluated in a restricted namespace. This means new distributions can be tried by editing a single YAML line — no Python changes required.

Two knobs control how the network is loaded:

- `num_apps` — create a fixed number of applications (set `saturation_percentage: null`).
- `saturation_percentage` — create applications until their total RAM demand reaches this fraction of the total infrastructure RAM (set `num_apps: null`).

Exactly one of them must be set.

## Outputs

For each simulation run, the folder `Simulations_raw/Sim_<timestamp>/` contains:

- **`Simulation{i}.json`** — one JSON file per iteration, with:
  - the state of users and applications **before** and **after** the event,
  - the event that fired and the global simulation time,
  - the optimal placement (`{app_name: node_id}`),
  - per-node information (RAM total, RAM used, running apps, enabled flag),
  - the total latency and the total RAM occupied,
  - a `diff_message` describing changes with respect to the previous placement.
- **`Simulation{i}_graph_before.gml`** and **`Simulation{i}_graph_after.gml`** — the NetworkX graph at each phase, stored in GML so it can be re-opened with `nx.read_gml(...)`.
- **`user_counts_log.csv`** — one row per iteration with `Iteration`, `User Count`, and `Action`.

The simulator halts automatically (via `stop_simulation`) if any iteration leaves the system with no applications, no users, no active nodes, or no active edges.

## Visualization

`visual_results.py` reads `user_counts_log.csv` and produces:

- the evolution of the number of users over iterations (a direct empirical check of Little's Law — the curve should oscillate around $L = \lambda W$),
- histograms of event counts per bin of 50 iterations, one per event family (`move_user`, `remove_user`, `new_user`, request-ratio events).

Before running it, edit the `path_mac` / `path_linux` variables at the top of the file to point at the simulation folder you want to analyze.

## Reproducibility

Randomness flows through four independent generators, all seeded from the master seed passed to `SimulationSet`:

```python
self.rng_graph = np.random.default_rng(master_seed)      # topology, node/edge events
self.rng_app   = np.random.default_rng(master_seed + 1)  # application attributes and events
self.rng_user  = np.random.default_rng(master_seed + 2)  # user attributes and events
self.rng_event = np.random.default_rng(master_seed + 3)  # new_object meta-events
```

Using one generator per domain keeps the random sequences isolated: adding a new event type or changing the order in which users are created does not perturb the graph topology, and vice versa. Running `main.py` twice with the same master seed and the same YAML file produces bit-identical outputs.

To change the seed, edit this line in `main.py`:

```python
sim_set = SimulationSet(master_seed=42)
```

## Extending the simulator

A few patterns worth knowing before modifying the code:

- **New action on an existing object** — add a method to the relevant set (`UserSet`, `ApplicationSet`, `InfrastructureSet`) and declare it under `attributes.<domain>.actions` in the YAML. The event loop dispatches by method name via `getattr`.
- **New event parameters** — declare them under `action_params` in the YAML; `EventSet.update_event_params` will inject live objects (e.g. the infrastructure, the event set itself) before the method is called.
- **New distribution family** — as long as it is a `numpy.random.Generator` method, it is usable in the YAML without any code change (e.g. `rng.lognormal(0, 1)`).
- **New graph model** — add a branch in `_generate_random_graph` in `infrastructure.py` and expose its parameters under `model_params` in the YAML.
- **Multi-resource ILP** — the current formulation uses only RAM as a capacity constraint. Adding CPU, disk, or bandwidth constraints requires extending `solve_application_placement` in `main.py` with additional constraints of the same form as the existing RAM constraint.

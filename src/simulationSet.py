import numpy as np
import logging
from typing import Any, Optional, Dict, Union, List
from .constants import DEFAULT_MASTER_SEED

logger = logging.getLogger(__name__)

class SimulationSet:
    def __init__(
        self,
        master_seed: int = DEFAULT_MASTER_SEED,
        seed_graph: Optional[int] = None,
        seed_app: Optional[int] = None,
        seed_user: Optional[int] = None,
        seed_event: Optional[int] = None,
        domain_seeds: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Initializes specific random generators for each simulation domain.
        Decoupling domain seeds allows keeping e.g. the same infrastructure
        (seed_graph) while changing the stochastic events (seed_event) or users.
        """
        if domain_seeds is None:
            domain_seeds = {}

        self.master_seed = master_seed
        self.seed_graph = seed_graph if seed_graph is not None else domain_seeds.get("graph", master_seed)
        self.seed_app = seed_app if seed_app is not None else domain_seeds.get("app", master_seed + 1)
        self.seed_user = seed_user if seed_user is not None else domain_seeds.get("user", master_seed + 2)
        self.seed_event = seed_event if seed_event is not None else domain_seeds.get("event", master_seed + 3)

        self.rng_graph = np.random.default_rng(self.seed_graph)
        self.rng_app = np.random.default_rng(self.seed_app)
        self.rng_user = np.random.default_rng(self.seed_user)
        self.rng_event = np.random.default_rng(self.seed_event)

    @classmethod
    def from_config(cls, config: Dict[str, Any], default_master_seed: int = DEFAULT_MASTER_SEED) -> 'SimulationSet':
        seeds_config = config.get('seeds', {})
        master = seeds_config.get('master', seeds_config.get('master_seed', default_master_seed))
        return cls(
            master_seed=master,
            seed_graph=seeds_config.get('graph'),
            seed_app=seeds_config.get('app'),
            seed_user=seeds_config.get('user'),
            seed_event=seeds_config.get('event'),
            domain_seeds=seeds_config,
        )

    def get_seeds_info(self) -> Dict[str, int]:
        return {
            "master_seed": self.master_seed,
            "graph": self.seed_graph,
            "app": self.seed_app,
            "user": self.seed_user,
            "event": self.seed_event,
        }

    def _get_rng_for_context(self, context: str) -> np.random.Generator:
        """Returns the appropriate generator based on the context string."""
        context = context.lower()
        if context in ['graph', 'graph_node', 'graph_edge', 'graph_creation']:
            return self.rng_graph
        elif context == 'app':
            return self.rng_app
        elif context == 'user':
            return self.rng_user
        elif context in ['event', 'global_spawner']:
            return self.rng_event
        else:
            raise ValueError(f"Unknown context: {context}")

    def choice(self, context: str, seq: List[Any]) -> Any:
        """Deterministically chooses one element from seq using the domain RNG."""
        if not seq:
            raise IndexError("Cannot choose from an empty sequence")
        rng = self._get_rng_for_context(context)
        idx = int(rng.integers(0, len(seq)))
        return seq[idx]

    def sample(self, context: str, seq: List[Any], k: int) -> List[Any]:
        """Deterministically samples k unique elements from seq using the domain RNG."""
        if not seq:
            return []
        k = min(k, len(seq))
        rng = self._get_rng_for_context(context)
        indices = rng.choice(len(seq), size=k, replace=False)
        return [seq[int(i)] for i in indices]

    def shuffle(self, context: str, seq: List[Any]) -> None:
        """Deterministically shuffles seq in-place using the domain RNG."""
        rng = self._get_rng_for_context(context)
        rng.shuffle(seq)

    def parse_distribution(self, dist_config: Union[int, float, str, Dict[str, Any], None], context: str, **kwargs: Any) -> Optional[Any]:
        """
        Parses and evaluates a distribution from a dictionary configuration.
        
        Args:
            dist_config: Can be a primitive value, or a dictionary like:
                         {"type": "normal", "loc": 10, "scale": 2.5}
            context (str): The domain ('graph', 'app', 'user', 'event')
            **kwargs: Variables to format into string parameters.
            
        Returns:
            The evaluated numeric value or array.
        """
        if dist_config is None or dist_config == 'None':
            return None

        # Return primitives immediately
        if isinstance(dist_config, (int, float)):
            return dist_config

        # If it's a string, attempt to cast to float. 
        # (This is mostly for backwards compatibility or simple literals)
        if isinstance(dist_config, str):
            try:
                return float(dist_config)
            except ValueError:
                logger.warning(f"Failed to parse primitive string '{dist_config}'. Returning None.")
                return None

        if isinstance(dist_config, dict):
            dist_type = dist_config.get("type")
            if not dist_type:
                logger.error("Distribution dictionary must contain a 'type' key.")
                return None
            
            rng = self._get_rng_for_context(context)
            
            # Security: Ensure we only call valid methods of the numpy random Generator
            if not hasattr(rng, dist_type):
                logger.error(f"Distribution '{dist_type}' is not a valid numpy random Generator method.")
                return None
                
            dist_method = getattr(rng, dist_type)
            if not callable(dist_method):
                logger.error(f"'{dist_type}' is not callable.")
                return None

            # Process parameters, applying formatting if they are strings
            dist_params = {}
            for k, v in dist_config.items():
                if k == "type" or isinstance(v, dict): continue
                if isinstance(v, str):
                    try:
                        v = v.format(**kwargs)
                        # Try casting to float/int if possible after formatting
                        try:
                            if "." in v:
                                v = float(v)
                            else:
                                v = int(v)
                        except ValueError:
                            pass # Leave as string if not castable
                    except KeyError as e:
                        logger.error(f"Missing formatting variable {e} for string: {v}")
                        return None
                
                # Parameter translation for numpy 'normal' generator
                if dist_type == "normal":
                    if k == "mean": k = "loc"
                    elif k == "sigma": k = "scale"

                dist_params[k] = v

            # Intercept scale for Weibull since numpy's weibull generator does not take a scale parameter directly
            weibull_scale = 1.0
            if dist_type == "weibull" and "scale" in dist_params:
                weibull_scale = float(dist_params.pop("scale"))

            try:
                val = dist_method(**dist_params)
                if dist_type == "weibull":
                    val = val * weibull_scale
                return val
            except Exception as e:
                logger.error(f"Error calling {dist_type} with params {dist_params}: {e}")
                return None
            
        return None
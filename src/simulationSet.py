import numpy as np
import logging
from typing import Any, Optional, Dict, Union
from .constants import DEFAULT_MASTER_SEED

logger = logging.getLogger(__name__)

class SimulationSet:
    def __init__(self, master_seed: int = DEFAULT_MASTER_SEED) -> None:
        """
        Initializes specific random generators for each simulation domain.
        Using a master seed ensures the whole simulation is reproducible.
        """
        self.master_seed = master_seed
        
        self.rng_graph = np.random.default_rng(master_seed)
        self.rng_app = np.random.default_rng(master_seed + 1)
        self.rng_user = np.random.default_rng(master_seed + 2)
        self.rng_event = np.random.default_rng(master_seed + 3)

    def _get_rng_for_context(self, context: str) -> np.random.Generator:
        """Returns the appropriate generator based on the context string."""
        context = context.lower()
        if context in ['graph', 'graph_node', 'graph_edge']:
            return self.rng_graph
        if context == 'graph_creation':
            # Backwards-compat: use the same RNG as 'graph' generation.
            # (Previously referenced a non-existent attribute.)
            return self.rng_graph
        elif context == 'app':
            return self.rng_app
        elif context == 'user':
            return self.rng_user
        elif context in ['event', 'global_spawner']:
            return self.rng_event
        else:
            raise ValueError(f"Unknown context: {context}")

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
                if k == "type": continue
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

            try:
                return dist_method(**dist_params)
            except Exception as e:
                logger.error(f"Error calling {dist_type} with params {dist_params}: {e}")
                return None
            
        return None
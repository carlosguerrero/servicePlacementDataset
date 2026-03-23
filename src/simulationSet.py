import numpy as np

class SimulationSet:
    def __init__(self, master_seed=42):
        """
        Initializes specific random generators for each simulation domain.
        Using a master seed ensures the whole simulation is reproducible.
        """
        self.master_seed = master_seed
        
        self.rng_graph = np.random.default_rng(master_seed)
        self.rng_app = np.random.default_rng(master_seed + 1)
        self.rng_user = np.random.default_rng(master_seed + 2)
        self.rng_event = np.random.default_rng(master_seed + 3)

    def _get_rng_for_context(self, context):
        """Returns the appropriate generator based on the context string."""
        context = context.lower()
        if context == 'graph':
            return self.rng_graph
        if context == 'graph_creation':
            return self.seed_graph_creation
        elif context == 'app':
            return self.rng_app
        elif context == 'user':
            return self.rng_user
        elif context in ['event', 'new_object']:
            return self.rng_event
        else:
            raise ValueError(f"Unknown context: {context}")

    def parse_distribution(self, dist_string, context, **kwargs):
        """
        Parses and evaluates a generic distribution string from the YAML file.
        
        Args:
            dist_string (str): The string from YAML (e.g., 'rng.uniform(0.1, 5.0)')
            context (str): The domain ('graph', 'app', 'user', 'event')
            **kwargs: Any variables to format into the string (like num_nodes=10)
            
        Returns:
            The evaluated numeric value or array.
        """
        if not dist_string or dist_string == 'None':
            return None

        try:
            formatted_str = dist_string.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing formatting variable {e} for string: {dist_string}")

        rng = self._get_rng_for_context(context)

        allowed_locals = {
            'rng': rng,
            'np': np
        }

        try:
            return eval(formatted_str, {"__builtins__": {}}, allowed_locals)
        except Exception as e:
            print(f"[Error] Failed to evaluate '{formatted_str}' in context '{context}'. Error: {e}")
            return None
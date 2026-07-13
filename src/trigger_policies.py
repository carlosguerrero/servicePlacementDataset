import numpy as np
from typing import Dict, Any, Optional

class TriggerPolicyManager:
    """
    Evaluates execution policies for the ILP solver to prevent continuous and unrealistic
    execution on every discrete event.
    """
    def __init__(self, config: Dict[str, Any], sim_set: Optional[Any] = None):
        self.config = config.get('trigger_policy', {'type': 'solve_all'})
        self.sim_set = sim_set
        self.event_counter = 0
        self.last_execution_time = 0.0

    def _is_critical_event(self, event: Dict[str, Any], critical_events: list) -> bool:
        # Check action or action_type
        actual_action = event.get('action_type', event.get('action'))
        if actual_action in critical_events:
            return True
            
        composed_of = event.get('impact', {}).get('composed_of', [])
        for sub_action in composed_of:
            if sub_action.get('action_type') in critical_events:
                return True
                
        return False

    def should_execute_ilp(self, event: Dict[str, Any], global_time: float) -> bool:
        self.event_counter += 1
        policy_type = self.config.get('type', 'solve_all')

        if policy_type == 'solve_all':
            return True
            
        elif policy_type == 'solve_none':
            return False
            
        elif policy_type == 'solve_random_prob':
            prob = self.config.get('probability', 0.05)
            if self.sim_set is not None:
                rand_val = float(self.sim_set.rng_event.random())
            else:
                rand_val = float(np.random.default_rng().random())
            return rand_val < prob
            
        elif policy_type == 'solve_time_windows':
            windows = self.config.get('windows', [])
            for w in windows:
                if w[0] <= global_time <= w[1]:
                    return True
            return False
            
        elif policy_type == 'solve_event_index_ranges':
            ranges = self.config.get('ranges', [])
            for r in ranges:
                if r[0] <= self.event_counter <= r[1]:
                    return True
            return False
            
        elif policy_type == 'solve_custom_pattern':
            pattern = self.config.get('pattern', [True])
            if not pattern:
                return True
            idx = (self.event_counter - 1) % len(pattern)
            return pattern[idx]
            
        elif policy_type == 'solve_every_t_seconds':
            interval = self.config.get('interval_seconds', 10.0)
            if global_time - self.last_execution_time >= interval:
                self.last_execution_time = global_time
                return True
            return False
            
        elif policy_type == 'solve_every_n_events':
            batch_size = self.config.get('batch_size', 50)
            if self.event_counter % batch_size == 0:
                return True
            return False
            
        elif policy_type == 'solve_on_event_types':
            critical_events = self.config.get('critical_events', [])
            return self._is_critical_event(event, critical_events)
            
        elif policy_type == 'combined':
            critical_events = self.config.get('critical_events', [])
            if self._is_critical_event(event, critical_events):
                self.last_execution_time = global_time
                return True
                
            interval = self.config.get('interval_seconds', 10.0)
            if global_time - self.last_execution_time >= interval:
                self.last_execution_time = global_time
                return True
            return False

        return True

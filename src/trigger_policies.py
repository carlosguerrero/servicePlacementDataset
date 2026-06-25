import random
from typing import Dict, Any

class TriggerPolicyManager:
    """
    Evaluates execution policies for the ILP solver to prevent continuous and unrealistic
    execution on every discrete event.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('trigger_policy', {'type': 'solve_all'})
        self.event_counter = 0
        self.last_execution_time = 0.0

    def should_execute_ilp(self, event: Dict[str, Any], global_time: float) -> bool:
        self.event_counter += 1
        policy_type = self.config.get('type', 'solve_all')

        if policy_type == 'solve_all':
            return True
            
        elif policy_type == 'solve_none':
            return False
            
        elif policy_type == 'solve_random_prob':
            prob = self.config.get('probability', 0.05)
            return random.random() < prob
            
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
            return event.get('action') in critical_events
            
        elif policy_type == 'combined':
            critical_events = self.config.get('critical_events', [])
            if event.get('action') in critical_events:
                self.last_execution_time = global_time
                return True
                
            interval = self.config.get('interval_seconds', 10.0)
            if global_time - self.last_execution_time >= interval:
                self.last_execution_time = global_time
                return True
            return False

        return True

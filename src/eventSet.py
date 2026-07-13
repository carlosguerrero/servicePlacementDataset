import uuid
import copy
import numpy as np
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventSet:
    def __init__(self) -> None:
        self.events: Dict[str, Dict[str, Any]] = {}
        self.global_time: float = 0.0
    
    def get_first_event(self) -> Optional[Dict[str, Any]]:
        if not self.events:
            return None
        
        min_id = min(self.events, key=lambda k: self.events[k]['time'])
        return self.events[min_id]

    def newEventItem(self, type_object: str, object_id: Optional[str], time: float, action: str, impact: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'type_object': type_object,
            'object_id': object_id,
            'time': time,
            'action': action,
            'impact': impact,
            'message': None
        }
    
    def add_event(self, eventAttributes: Dict[str, Any], sim_set: Optional[Any] = None) -> str:
        if sim_set is not None:
            random_bytes = sim_set.rng_event.bytes(16)
            event_id = str(uuid.UUID(bytes=random_bytes))
        else:
            event_id = str(uuid.uuid4())
        eventAttributes['id'] = event_id
        self.events[event_id] = eventAttributes
        return event_id
    
    def remove_event(self, event_id: str) -> bool:
        if event_id in self.events:
            del self.events[event_id]
            return True
        return False



    def remove_events_by_object_id(self, object_id: str) -> None:
        events_to_delete = [
            event_id
            for event_id, value in self.events.items()
            if value['object_id'] == object_id
        ]

        for event_id in events_to_delete:
            self.remove_event(event_id)
    
    def update_event_time(self, event_id: str, config: Dict[str, Any], sim_set: Any) -> None:
        # Update time
        if event_id not in self.events.keys():
            logger.debug("The event was deleted from event_list")
            return
        
        impact = self.events[event_id].get('impact') or {}
        is_implicit = impact.get('is_implicit', False)
        if is_implicit:
            self.remove_event(event_id)
            logger.debug(f"Implicit event {event_id} removed after execution")
            return

        # We just need to get a new time from config + global_time
        actual_type_object = self.events[event_id]['type_object']
        actual_action = self.events[event_id]['action']
        
        delay = get_time(config, actual_type_object, actual_action, sim_set)
        if delay == 0.0:
            self.remove_event(event_id)
            logger.debug(f"Event {event_id} removed because it has no recurring frequency")
            return
            
        self.events[event_id]['time'] = delay + self.global_time
        logger.debug(f"Updated time for event {event_id}: {self.events[event_id]['time']}")

    def __str__(self) -> str:
        """Returns a string representation of the EventSet (the events list) without impact."""
        events_to_print = {}
        for event_id, event in self.events.items():
            event_copy = {k: v for k, v in event.items() if k != 'impact'}
            events_to_print[event_id] = event_copy
        return str(events_to_print)
        # return str(self.events)

def generate_events(object_item: Dict[str, Any], type_object: str, event_set: EventSet, sim_set: Any) -> EventSet:
    """
    object_item: A dictionary containing {'id': ..., 'actions': ...} 
                 (Works for User items, App items, and the new Infrastructure items)
    type_object: 'user', 'app', or 'graph' 
    event_set: The EventSet instance where the generated events will be added.
    seed: Optional seed for random number generation to ensure reproducibility.
    """
    obj_id = object_item['id']
    actions_dict = object_item['actions']

    for action_name, action_details in actions_dict.items():
        distribution_str = action_details.get('frequency', '0')
        delay_val = sim_set.parse_distribution(distribution_str, context=type_object)
        if delay_val is None:
            delay_val = 0.0
        
        eventAttributes = event_set.newEventItem(
            object_id=obj_id,
            type_object=type_object,
            time=round(delay_val, 2) + event_set.global_time,
            action=action_name,
            impact=copy.deepcopy(action_details.get('impact', {}))  # Use deepcopy
        )
        eventAttributes['action_type'] = action_details.get('action_type', action_name)
        event_set.add_event(eventAttributes, sim_set=sim_set)

    return event_set

def init_global_spawner(config: Dict[str, Any], event_set: EventSet, sim_set: Any) -> EventSet:
    """Initializes events for creating new objects (users and apps) based on the configuration."""
    attributes = config
    global_spawner_conf = attributes.get('global_spawner', {})
    actions_conf = global_spawner_conf.get('actions', {})
    
    # Retrocompatibility if 'actions' key is not used
    if not actions_conf and global_spawner_conf:
        for action, type_conf in global_spawner_conf.items():
            if action == 'actions': continue
            type_object = action.removeprefix("new_")
            delay_val = sim_set.parse_distribution(type_conf['frequency'], context=type_object)
            if delay_val is None:
                delay_val = 0.0
            eventAttributes = event_set.newEventItem(
                object_id=None,
                type_object=type_object,
                time = round(delay_val, 2) + event_set.global_time, 
                action = action,
                impact = type_conf.get('impact')
            )
            eventAttributes['action_type'] = action
            event_set.add_event(eventAttributes, sim_set=sim_set)
        return event_set

    for action_name, type_conf in actions_conf.items():
        type_object = type_conf.get('type_object', 'global')
        actual_action = type_conf.get('action_type', action_name)
        delay_val = sim_set.parse_distribution(type_conf.get('frequency', '0'), context=type_object)
        if delay_val is None:
            delay_val = 0.0
            
        eventAttributes = event_set.newEventItem(
            object_id=None,
            type_object=type_object,
            time = round(delay_val, 2) + event_set.global_time, 
            action = action_name,
            impact = copy.deepcopy(type_conf.get('impact', {}))
        )
        eventAttributes['action_type'] = actual_action
        event_set.add_event(eventAttributes, sim_set=sim_set)

    return event_set

def get_time(config: Dict[str, Any], type_object: str, action_name: str, sim_set: Any) -> float:
    """
    Retrieves a time value by evaluating the distribution string 
    found in the config file for a specific object and action.
    """
    attributes = config

    # Check if the action is from global_spawner
    global_spawner_conf = attributes.get('global_spawner', {})
    actions_conf = global_spawner_conf.get('actions', {})
    
    if action_name in actions_conf:
        specific_action_conf = actions_conf.get(action_name, {})
        distr_string = specific_action_conf.get('frequency')
    elif action_name in global_spawner_conf and action_name != 'actions':
        # Retrocompatibility
        specific_action_conf = global_spawner_conf.get(action_name, {})
        distr_string = specific_action_conf.get('frequency')
    else:
        obj_conf = attributes.get(type_object, {})
        actions_conf = obj_conf.get('actions', {})
        specific_action_conf = actions_conf.get(action_name, {})
        distr_string = specific_action_conf.get('frequency')
        
    if distr_string:
        try:
            # explicit dictionary ensures eval has access to the 'random' module
            parsed = sim_set.parse_distribution(distr_string, context=type_object)
            if parsed is None:
                parsed = 0.0
            return parsed
        except Exception as e:
            logger.error(f"Error evaluating distribution '{distr_string}' for {action_name}: {e}")
            return 0.0
                
    # No distribution found -> no additional delay
    return 0.0


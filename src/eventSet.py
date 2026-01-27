import uuid
import random
import copy

class EventSet:
    def __init__(self):
        self.events = {}
        self.global_time = 0
    
    def get_first_event(self):
        if not self.events:
            return None
        
        min_id = min(self.events, key=lambda k: self.events[k]['time'])
        # BORRAR: first_id = next(iter(self.events))
        return self.events[min_id]

    def newEventItem(self, type_object, object_id, time, action, action_params):
        return {
            'type_object': type_object,
            'object_id': object_id,
            'time': time,
            'action': action,
            'action_params': action_params
        }
    
    def add_event(self, eventAttributes):
        event_id = str(uuid.uuid4()) 
        eventAttributes['id'] = event_id
        self.events[event_id] = eventAttributes
        return event_id
    
    def remove_event(self, event_id):
        if event_id in self.events:
            del self.events[event_id]
            return True
        return False

    def update_event_params(self, event_id, config, app_set, user_set, infrastructure):
        event = self.events[event_id]
        params = event.get('action_params')

        if not isinstance(params, dict):
            return

        params_map = {
            'infrastructure': infrastructure,
            'config': config,
            'app_set': app_set,
            'user_set': user_set,
            'event_set': self.events
        }

        for key, obj_value in params_map.items():
            if key in params:
                params[key] = obj_value

    def remove_events_by_object_id(self, object_id):
        events_to_delete = [
            event_id
            for event_id, value in self.events.items()
            if value['object_id'] == object_id
        ]

        for event_id in events_to_delete:
            self.remove_event(event_id)
        
        print("DESDE event - remove_events_by_object_id:", object_id, "has been removed")
        print("Number of events that have been deleted:", len(events_to_delete))
    
    def update_event_time(self, event_id, config):
        if event_id in self.events.keys():
            # We just need to get a new time from config + global_time
            actual_type_object = self.events[event_id]['type_object']
            actual_action = self.events[event_id]['action']
            self.events[event_id]['time'] = get_time(config, actual_type_object, actual_action) + self.global_time
            print("DESDE event - update_event_time: The", self.events[event_id]['action'], "for the type of object", self.events[event_id]['type_object'], "has been updated to time", self.events[event_id]['time'])

        else:
            print("DESDE eventSet - update_event: El event_id no estaba en la event_list")
        print("Update event list después update:", self)
        print(" ")

    def __str__(self):
        """Returns a string representation of the EventSet (the events list) without action_params."""
        events_to_print = {}
        for event_id, event in self.events.items():
            event_copy = {k: v for k, v in event.items() if k != 'action_params'}
            events_to_print[event_id] = event_copy
        return str(events_to_print)
        # return str(self.events)

# BORRAR
def generate_events2(object, type_object, event_set):
    """type_object: 'user' or 'app'
    Later will be also be node"""
    for action in object['actions']:
        eventAttributes = event_set.newEventItem(
            object_id=object['id'],
            type_object=type_object,
            time = round(eval(object['actions'][action]['distribution']), 2) + event_set.global_time, 
            action = action,
            action_params = object['actions'][action]['action_params']
        )
        event_set.add_event(eventAttributes)

    return event_set

def generate_events(object, type_object, event_set):
    """
    type_object: 'user', 'app', or 'graph'
    """
    if type_object == 'graph':
        # For the graph
        obj_id = "000" 
        actions_dict = object.actions  # Accessing self.actions from the class
    else:
        # For users/apps 
        obj_id = object['id']
        actions_dict = object['actions']

    for action_name, action_details in actions_dict.items():
        distribution_str = action_details.get('distribution', '0')
        delay_val = eval(str(distribution_str))
        
        eventAttributes = event_set.newEventItem(
            object_id=obj_id,
            type_object=type_object,
            time=round(delay_val, 2) + event_set.global_time,
            action=action_name,
            action_params=action_details.get('action_params', {})
        )
        event_set.add_event(eventAttributes)

    return event_set

def init_new_object(config, event_set):
    """type_object: 'user' or 'app'
    Later will be also be node"""
    attributes = config.get('attributes', {})
    new_object_conf = attributes.get('new_object', {})
    for action, type_conf in new_object_conf.items():
        eventAttributes = event_set.newEventItem(
            object_id=None,
            type_object=action.removeprefix("new_"),
            time = round(eval(type_conf['distribution']), 2) + event_set.global_time, 
            action = action,
            action_params = type_conf['action_params']
        )
        event_set.add_event(eventAttributes)

    return event_set

def get_time(config, type_object, action_name):
    """
    Retrieves a time value by evaluating the distribution string 
    found in the config file for a specific object and action.
    """
    attributes = config.get('attributes', {})

    if action_name.startswith('new'):
        obj_conf = attributes.get('new_object', {})
        actions_conf = obj_conf.get(action_name, {})
        distr_string = actions_conf.get('distribution')
    else:
        obj_conf = attributes.get(type_object, {})
        actions_conf = obj_conf.get('actions', {})
        specific_action_conf = actions_conf.get(action_name, {})
        distr_string = specific_action_conf.get('distribution')
        
    if distr_string:
        try:
            # explicit dictionary ensures eval has access to the 'random' module
            return eval(distr_string, {"random": random})
        except Exception as e:
            print(f"Error evaluating distribution '{distr_string}' for {action_name}: {e}")
            return 0.0
                
    return False


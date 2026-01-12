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

    # BORRAR
    # def update_event_params(self, event_id, config, app_set, user_set, infrastructure):
    #     if self.events[event_id]['action'].startswith('move'):
    #         print("DESDE move: The", self.events[event_id]['type_object'], "with id", self.events[event_id]['object_id'], "has been removed")
    #         self.events[event_id]['action_params']['infrastructure'] = infrastructure
    #     elif self.events[event_id]['action'].startswith('new'):
    #         print("DESDE new: A new", self.events[event_id]['type_object'], "will be created")
    #         self.events[event_id]['action_params']['config'] = config
    #         self.events[event_id]['action_params']['app_set'] = app_set
    #         self.events[event_id]['action_params']['user_set'] = user_set
    #         self.events[event_id]['action_params']['infrastructure'] = infrastructure
    #     print("Update event list después update:", self.events)
    #     print(" ")

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
    
    def update_event(self, event_id):

        if self.events[event_id]['action'].startswith('remove'):
            id_to_remove = self.events[event_id]['object_id']
            print("DESDE remove: The", self.events[event_id]['type_object'], "with id", id_to_remove, "has been removed")

            events_to_delete = [
                event_id
                for event_id, value in self.events.items()
                if value['object_id'] == id_to_remove
            ]
            print("Events to delete:", events_to_delete)

            for event_id in events_to_delete:
                self.remove_event(event_id)

            # events_copy = copy.deepcopy(self.events)
            # for event in events_copy.values():
            #     if event['object_id'] == self.events[event_id]['object_id']:
            #         self.remove_event(event['id'])

        elif self.events[event_id]['action'].startswith('move'):
            print("DESDE move: The", self.events[event_id]['type_object'], "with id", self.events[event_id]['object_id'], "has been removed")
            self.remove_event(event_id)

        print("Update event list después update:", self)
        print(" ")
        # user_set.move_user(event[1]['id'])) # por graph
        # Hay que actualizar el nodo al que está conectado el usuario
        # y también hay que asignar un nuevo tiempo: random time + global_time
        # Aquí añadiré lo de elegir un nuevo nodo
        # y asignar un nuevo tiempo

    def __str__(self):
        """Returns a string representation of the EventSet (the events list) without action_params."""
        events_to_print = {}
        for event_id, event in self.events.items():
            event_copy = {k: v for k, v in event.items() if k != 'action_params'}
            events_to_print[event_id] = event_copy
        return str(events_to_print)
        # return str(self.events)

def generate_events(object, type_object, event_set):
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

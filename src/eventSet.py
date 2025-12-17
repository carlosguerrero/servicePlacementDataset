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

        print("Update event list después update:", self.events)
        print(" ")
        # user_set.move_user(event[1]['id'])) # por graph
        # Hay que actualizar el nodo al que está conectado el usuario
        # y también hay que asignar un nuevo tiempo: random time + global_time
        # Aquí añadiré lo de elegir un nuevo nodo
        # y asignar un nuevo tiempo

    def __str__(self):
        """Returns a string representation of the EventSet (the events list)."""
        return str(self.events)

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

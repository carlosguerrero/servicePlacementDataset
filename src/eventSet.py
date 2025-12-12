import uuid
import random

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

    def newEventItem(self, type_object, object_id, time, action):
        return {
            'type_object': type_object,
            'object_id': object_id,
            'time': time,
            'action': action
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
            action = action
        )
        event_set.add_event(eventAttributes)

    return event_set

if __name__ == "__main__":
    event_set = EventSet()
    print(event_set)
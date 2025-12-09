import uuid

class EventSet:
    def __init__(self):
        self.events = {}
        self.global_time = 0

    def sort_by_time(self):
        # 1. Get items, 2. Sort them by time, 3. Convert back to dict
        self.events = dict(sorted(
            self.events.items(), 
            key=lambda item: item[1]['time']
        ))
    
    def get_first_event(self):
        if not self.events:
            return None
            
        first_id = next(iter(self.events))
        return self.events[first_id]

    def newUserItem(self, type_object, object_id, time, action):
        """Creates a new user item with the given attributes."""
        return {
            'type_object': type_object,
            'object_id': object_id,
            'time': time,
            'action': action
        }
    
    def add_event(self, eventAttributes):
        """Adds a new user to the set."""
        event_id = str(uuid.uuid4())  # Generates a unique identifier
        eventAttributes['id'] = event_id
        self.events[event_id] = eventAttributes
        return event_id
    
    def remove_event(self, event_id):
        """Removes a user from the set based on its ID."""
        if event_id in self.events:
            del self.events[event_id]
            return True
        return False

    def __str__(self):
        """Returns a string representation of the EventSet (the events list)."""
        return str(self.events)

def generate_events(objects_list, type_object, event_set):
    """type_object: 'user' or 'app'
    Later will be also be node"""

    for i in eval('objects_list' + '.get_all_' + type_object + 's().values()'):
        eventAttributes = event_set.newUserItem(
            object_id=i['id'],
            type_object=type_object,
            time = i['time'] + event_set.global_time, # BORRAR: puede dar problemas
            action = i['action']
        )
        event_set.add_event(eventAttributes)
    return event_set
import uuid

class UserSet:
    def __init__(self):
        self.users = {}

    def newUserItem(self, name, requestedApp, appName, requestRatio, connectedTo):
        """Creates a new user item with the given attributes."""
        return {
            'name': name,
            'requestedApp': requestedApp,
            'appName': appName,
            'requestRatio': requestRatio,
            'connectedTo': connectedTo
        }

    def getAllUsersByApp(self, appId):
        """Returns all users that requested a specific application."""
        return [user for user in self.users.values() if user['requestedApp'] == appId]
    
    def getAllUsersByNode(self, nodeId):
        """Returns all users connected to a specific node."""
        return [user for user in self.users.values() if user['connectedTo'] == nodeId]

    def add_user(self, userAttributes):
        """Adds a new user to the set."""
        user_id = str(uuid.uuid4())  # Generates a unique identifier
        userAttributes['id'] = user_id
        self.users[user_id] = userAttributes
        return user_id

    def remove_user_by_requested_app(self, requested_app):
        """Removes a user from the set based on their requested application."""
        for user_id, user in list(self.users.items()):
            if user['requestedApp'] == requested_app:
                del self.users[user_id]
                return True
        return False
    
    def remove_user(self, user_id):
        """Removes a user from the set based on its ID."""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False

    def get_user(self, user_id):
        """Retrieves a user by their ID from the set."""
        return self.users.get(user_id)

    def get_all_users(self):
        """Returns all users in the set."""
        return self.users

    def __str__(self):
        """Returns a string representation of the UserSet (the users dictionary)."""
        return str(self.users)

    def __repr__(self):
        """Official string representation for developers (useful for debugging)."""
        return f"UserSet(users={self.users})"
    



if __name__ == "__main__":
    userset = UserSet()

    # Create and add users
    user1 = userset.newUserItem("Alice", requestedApp=1, appName="AppOne", requestRatio=0.5, connectedTo=101)
    user2 = userset.newUserItem("Bob", requestedApp=2, appName="AppTwo", requestRatio=0.8, connectedTo=102)

    id1 = userset.add_user(user1)
    id2 = userset.add_user(user2)

    print("\nAll Users:")
    print(userset.get_all_users())

    print("\nUsers requesting App 1:")
    print(userset.getAllUsersByApp(1))

    print("\nUsers connected to Node 102:")
    print(userset.getAllUsersByNode(102))

    print("\nGet user by ID:")
    print(userset.get_user(id1))

    print("\nRemove user by requested app (App 1):")
    userset.remove_user_by_requested_app(1)
    print(userset.get_all_users())

    print("\nRemove user by ID:")
    userset.remove_user(id2)
    print(userset.get_all_users())

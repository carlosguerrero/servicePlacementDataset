from typing import TypedDict, Any, Dict, Optional, Union

class AppItem(TypedDict):
    name: str
    popularity: float
    cpu: float
    ram: float
    disk: float
    time: float
    actions: Dict[str, Any]
    id: str

class UserItem(TypedDict):
    name: str
    requestedApp: str
    appName: Optional[str]
    requestRatio: float
    connectedTo: Any
    centrality: float
    id: str

class EventItem(TypedDict):
    id: str
    type_object: str
    object_id: Optional[str]
    time: float
    action: str
    impact: Dict[str, Any]
    message: Optional[str]

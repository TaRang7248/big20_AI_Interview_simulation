# from pydantic import BaseModel
# from typing import Literal, Dict, Any, Optional

# ClientEventType = Literal["session.start", "session.stop"]

# class ClientEvent(BaseModel):
#     type: ClientEventType
#     session_id: Optional[str] = None
#     payload: Dict[str, Any] = {}

# ServerEventType = Literal["session.ready", "status", "error"]

# class ServerEvent(BaseModel):
#     type: ServerEventType
#     session_id: str
#     payload: Dict[str, Any]

from pydantic import BaseModel
from typing import Any, Dict, Literal, Optional

ClientEventType = Literal["session.start", "answer", "session.stop"]

class ClientEvent(BaseModel):
    type: ClientEventType
    payload: Dict[str, Any] = {}
    session_id: Optional[str] = None

ServerEventType = Literal["session.ready", "question", "debug", "error"]

class ServerEvent(BaseModel):
    type: ServerEventType
    session_id: str
    payload: Dict[str, Any]

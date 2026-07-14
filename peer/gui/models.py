from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConversationType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"
    BROADCAST = "broadcast"


@dataclass(slots=True)
class ChatMessage:
    conversation_id: str
    conversation_type: ConversationType
    sender: str
    content: str
    timestamp: str
    outgoing: bool = False
    status: str = "sent"


@dataclass(slots=True)
class Conversation:
    conversation_id: str
    title: str
    conversation_type: ConversationType
    subtitle: str = ""
    online: bool = True
    messages: list[ChatMessage] = field(default_factory=list)
    unread: int = 0


def current_time() -> str:
    return datetime.now().strftime("%H:%M:%S")

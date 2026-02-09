from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Turn:
    turn: int
    question: str
    q_type: str
    user_answer: str

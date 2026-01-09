from datetime import datetime
from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    email: str
    created_at: datetime
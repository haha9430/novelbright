from typing import Dict, List, Optional
from datetime import datetime

from app.models.entities import User


class UserRepository:
    def __init__(self):
        self._users_memory_db: Dict[int, User] = {}
        self._next_id = 1

    def save(self, name: str, email: str) -> User:
        user = User(
            id=self._next_id,
            name=name,
            email=email,
            created_at=datetime.now()
        )
        self._users_memory_db[self._next_id] = user
        self._next_id += 1
        return user

    def find_by_id(self, user_id: int) -> Optional[User]:
        return self._users_memory_db.get(user_id)

    def find_by_email(self, email: str) -> Optional[User]:
        for user in self._users_memory_db.values():
            if user.email == email:
                return user
        return None

    def find_all(self) -> List[User]:
        return list(self._users_memory_db.values())

    def delete(self, user_id: int) -> bool:
        if user_id in self._users_memory_db:
            del self._users_memory_db[user_id]
            return True
        return False
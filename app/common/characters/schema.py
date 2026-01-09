from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Relationship:
    target_id: str
    type: str
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Character:
    id: str
    name: str
    birthdate_or_age: str = ""   # "24" or "2002-03-01" 등 자유
    gender: str = ""
    occupation: str = ""

    core_features: List[str] = field(default_factory=list)           # 3개 정도 권장
    personality_strengths: List[str] = field(default_factory=list)    # 3개 권장
    personality_weaknesses: List[str] = field(default_factory=list)   # 3개 권장

    external_goal: str = ""
    internal_goal: str = ""
    trauma_weakness: str = ""
    speech_habit: str = ""

    relationships: List[Relationship] = field(default_factory=list)
    additional_settings: Dict[str, Any] = field(default_factory=dict)

    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["relationships"] = [r.to_dict() for r in self.relationships]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Character":
        rels = [Relationship(**r) for r in d.get("relationships", [])]
        return Character(
            id=d["id"],
            name=d.get("name", ""),
            birthdate_or_age=d.get("birthdate_or_age", ""),
            gender=d.get("gender", ""),
            occupation=d.get("occupation", ""),
            core_features=list(d.get("core_features", [])),
            personality_strengths=list(d.get("personality_strengths", [])),
            personality_weaknesses=list(d.get("personality_weaknesses", [])),
            external_goal=d.get("external_goal", ""),
            internal_goal=d.get("internal_goal", ""),
            trauma_weakness=d.get("trauma_weakness", ""),
            speech_habit=d.get("speech_habit", ""),
            relationships=rels,
            additional_settings=dict(d.get("additional_settings", {})),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )

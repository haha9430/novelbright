from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class RelatedEntity:
    relation_type: str          # 예: "participant", "cause"
    target_id: Optional[str] = None  # ID는 나중에 연결될 수도 있으므로 Optional
    target_name: str = ""       # ID가 없을 때 사용할 이름 (예: "세종대왕")
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HistoricalEntity:
    id: str
    name: str              # 예: "임진왜란", "이순신"
    entity_type: str       # 예: "Event", "Person", "Artifact"

    era: str = ""          # 예: "1592", "조선 중기"

    # 핵심 정보
    summary: str = ""      # 한 줄 요약
    description: str = ""  # 상세 설명

    # 메타 데이터
    tags: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    # 관계 (사건-인물, 사건-장소 등)
    related_entities: List[RelatedEntity] = field(default_factory=list)

    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["related_entities"] = [r.to_dict() for r in self.related_entities]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "HistoricalEntity":
        # 여기가 핵심: 딕셔너리 데이터를 객체로 바꿀 때 안전하게 처리
        rels_data = d.get("related_entities", [])
        clean_rels = []

        for r in rels_data:
            # 스키마에 정의된 필드만 뽑아서 RelatedEntity 생성 (불필요한 키가 있어도 무시하거나 기본값 처리)
            clean_rels.append(RelatedEntity(
                relation_type=r.get("relation_type", "unknown"),
                target_id=r.get("target_id"),      # None일 수 있음
                target_name=r.get("target_name", ""),
                description=r.get("description", "")
            ))

        return HistoricalEntity(
            id=d["id"],
            name=d.get("name", ""),
            entity_type=d.get("entity_type", "Unknown"),
            era=d.get("era", ""),
            summary=d.get("summary", ""),
            description=d.get("description", ""),
            tags=list(d.get("tags", [])),
            sources=list(d.get("sources", [])),
            related_entities=clean_rels,
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .schema import Character, Relationship
from .storage import read_json, write_json_atomic


KST = timezone(timedelta(hours=9))


def _now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _default_db() -> Dict[str, Any]:
    return {
        "meta": {"version": 1, "updated_at": _now_iso()},
        "characters": []
    }


def _next_id(existing_ids: List[str]) -> str:
    """
    char_001, char_002 ... 형식 자동 생성
    """
    nums = []
    for cid in existing_ids:
        if cid.startswith("char_"):
            tail = cid.replace("char_", "")
            if tail.isdigit():
                nums.append(int(tail))
    n = (max(nums) + 1) if nums else 1
    return f"char_{n:03d}"


def init_db(db_path: str) -> None:
    data = read_json(db_path)
    if not data:
        write_json_atomic(db_path, _default_db())


def _load(db_path: str) -> Dict[str, Any]:
    data = read_json(db_path)
    if not data:
        data = _default_db()
        write_json_atomic(db_path, data)
    if "characters" not in data:
        data["characters"] = []
    if "meta" not in data:
        data["meta"] = {"version": 1, "updated_at": _now_iso()}
    return data


def _save(db_path: str, data: Dict[str, Any]) -> None:
    data["meta"]["updated_at"] = _now_iso()
    write_json_atomic(db_path, data)


def list_characters(db_path: str) -> List[Dict[str, Any]]:
    data = _load(db_path)
    return list(data["characters"])


def get_character(db_path: str, character_id: str) -> Optional[Dict[str, Any]]:
    data = _load(db_path)
    for c in data["characters"]:
        if c.get("id") == character_id:
            return c
    return None


def create_character(db_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload에 id를 안 주면 자동 생성.
    """
    data = _load(db_path)
    existing_ids = [c.get("id", "") for c in data["characters"]]
    cid = payload.get("id") or _next_id(existing_ids)

    if any(c.get("id") == cid for c in data["characters"]):
        raise ValueError(f"Character id already exists: {cid}")

    now = _now_iso()
    payload = dict(payload)
    payload["id"] = cid
    payload.setdefault("created_at", now)
    payload.setdefault("updated_at", now)

    # relationships 정리(있으면)
    rels = payload.get("relationships", [])
    if rels:
        payload["relationships"] = [
            Relationship(**r).to_dict() if isinstance(r, dict) else r
            for r in rels
        ]

    data["characters"].append(payload)
    _save(db_path, data)
    return payload


def update_character(db_path: str, character_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    data = _load(db_path)
    for i, c in enumerate(data["characters"]):
        if c.get("id") == character_id:
            updated = dict(c)
            updated.update(patch)
            updated["id"] = character_id  # id는 고정
            updated["updated_at"] = _now_iso()

            # relationships 정리(있으면)
            if "relationships" in patch:
                rels = patch.get("relationships") or []
                updated["relationships"] = [
                    Relationship(**r).to_dict() if isinstance(r, dict) else r
                    for r in rels
                ]

            data["characters"][i] = updated
            _save(db_path, data)
            return updated
    raise KeyError(f"Character not found: {character_id}")


def delete_character(db_path: str, character_id: str) -> bool:
    data = _load(db_path)
    before = len(data["characters"])
    data["characters"] = [c for c in data["characters"] if c.get("id") != character_id]

    # 다른 캐릭터 관계에서 target_id로 참조하던 것도 제거(깨진 참조 방지)
    for c in data["characters"]:
        rels = c.get("relationships", []) or []
        c["relationships"] = [r for r in rels if r.get("target_id") != character_id]

    after = len(data["characters"])
    if after == before:
        return False
    _save(db_path, data)
    return True


def add_relationship(
    db_path: str,
    source_id: str,
    target_id: str,
    rel_type: str,
    summary: str = ""
) -> Dict[str, Any]:
    data = _load(db_path)

    src = None
    tgt_exists = False
    for c in data["characters"]:
        if c.get("id") == source_id:
            src = c
        if c.get("id") == target_id:
            tgt_exists = True

    if src is None:
        raise KeyError(f"Source character not found: {source_id}")
    if not tgt_exists:
        raise KeyError(f"Target character not found: {target_id}")

    rels = src.get("relationships", []) or []
    # 동일 target_id + type 중복 방지
    for r in rels:
        if r.get("target_id") == target_id and r.get("type") == rel_type:
            # 이미 있으면 summary만 업데이트
            r["summary"] = summary
            src["relationships"] = rels
            src["updated_at"] = _now_iso()
            _save(db_path, data)
            return src

    rels.append(Relationship(target_id=target_id, type=rel_type, summary=summary).to_dict())
    src["relationships"] = rels
    src["updated_at"] = _now_iso()
    _save(db_path, data)
    return src


def remove_relationship(db_path: str, source_id: str, target_id: str, rel_type: Optional[str] = None) -> Dict[str, Any]:
    data = _load(db_path)
    for c in data["characters"]:
        if c.get("id") == source_id:
            rels = c.get("relationships", []) or []
            if rel_type is None:
                rels = [r for r in rels if r.get("target_id") != target_id]
            else:
                rels = [r for r in rels if not (r.get("target_id") == target_id and r.get("type") == rel_type)]
            c["relationships"] = rels
            c["updated_at"] = _now_iso()
            _save(db_path, data)
            return c
    raise KeyError(f"Source character not found: {source_id}")


def to_dict(db_path: str) -> Dict[str, Any]:
    return _load(db_path)

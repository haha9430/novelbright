from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import difflib  # <--- [중요] 이 줄이 꼭 추가되어야 합니다!

from .schema import HistoricalEntity, RelatedEntity
from .storage import read_json, write_json_atomic

# 한국 시간(KST) 설정
KST = timezone(timedelta(hours=9))

def _now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")

def _default_db() -> Dict[str, Any]:
    return {
        "meta": {"version": 1, "updated_at": _now_iso()},
        "entities": []
    }

def _next_id(existing_ids: List[str]) -> str:
    nums = []
    for eid in existing_ids:
        if eid.startswith("hist_"):
            tail = eid.replace("hist_", "")
            if tail.isdigit():
                nums.append(int(tail))
    n = (max(nums) + 1) if nums else 1
    return f"hist_{n:04d}"

def init_db(db_path: str) -> None:
    data = read_json(db_path)
    if not data:
        write_json_atomic(db_path, _default_db())

def _load(db_path: str) -> Dict[str, Any]:
    data = read_json(db_path)
    if not data:
        data = _default_db()
        write_json_atomic(db_path, data)
    if "entities" not in data:
        data["entities"] = []
    return data

def _save(db_path: str, data: Dict[str, Any]) -> None:
    data["meta"]["updated_at"] = _now_iso()
    write_json_atomic(db_path, data)

# --- 조회 기능 ---

def list_entities(db_path: str) -> List[Dict[str, Any]]:
    data = _load(db_path)
    return list(data["entities"])

def get_entity(db_path: str, entity_id: str) -> Optional[Dict[str, Any]]:
    data = _load(db_path)
    for e in data["entities"]:
        if e.get("id") == entity_id:
            return e
    return None

def normalize_string(s: str) -> str:
    """비교를 위해 특수문자와 공백을 제거하는 헬퍼 함수"""
    # 점(·), 쉼표(,), 공백, 하이픈 등을 모두 제거하고 소문자로 변환
    special_chars = "·,.-_ []{}()"
    result = str(s).lower()
    for char in special_chars:
        result = result.replace(char, "")
    return result

def find_id_by_name(db_path: str, name: str) -> Optional[str]:
    """
    이름으로 ID 찾기 (최종_진짜_최종.ver)
    1. 정확한 일치
    2. 공백/특수문자 제거 후 일치
    3. 포함 관계 (Substring)
    4. [강력] 순서대로 글자가 포함된 경우 (Subsequence) -> 홍유릉 해결!
    5. 유사도 검색 (Fuzzy Match, 기준 완화)
    """
    target_raw = (name or "").strip()
    if not target_raw:
        return None

    data = _load(db_path)
    entities = data["entities"]

    # 1. [정확도 100%] 정확한 일치
    for e in entities:
        if e.get("name") == target_raw:
            return e.get("id")

    # 정규화 (공백/특수문자 제거)
    target_norm = normalize_string(target_raw)

    # 2. [정확도 90%] 정규화 일치 ("홍 릉" == "홍릉")
    for e in entities:
        if normalize_string(e.get("name")) == target_norm:
            return e.get("id")

    # 3. [정확도 80%] 포함 관계 ("홍릉" in "홍릉·유릉")
    for e in entities:
        e_norm = normalize_string(e.get("name"))
        if target_norm in e_norm: # 검색어가 DB 이름보다 짧을 때
            return e.get("id")
        if e_norm in target_norm: # DB 이름이 검색어보다 짧을 때
            return e.get("id")

    # 4. [정확도 70%] 순서대로 글자가 있는지 확인 (줄임말 해결사!)
    # 예: "홍유릉" -> "홍"릉·"유릉" (O)
    for e in entities:
        e_norm = normalize_string(e.get("name"))
        # target_norm의 글자들이 e_norm 안에 순서대로 모두 있는지 확인
        it = iter(e_norm)
        if all(char in it for char in target_norm):
            print(f"   (알림) 줄임말 매칭 성공: '{target_raw}' -> '{e['name']}'")
            return e.get("id")

    # 5. [최후의 수단] 유사도 검색 (기준을 0.6 -> 0.3으로 대폭 완화)
    import difflib
    entity_names = [e.get("name", "") for e in entities]
    # cutoff를 0.3으로 낮춰서 길이 차이가 나도 찾도록 함
    matches = difflib.get_close_matches(target_raw, entity_names, n=1, cutoff=0.3)

    if matches:
        best_match = matches[0]
        print(f"   (알림) 유사도 검색 성공: '{target_raw}' ~= '{best_match}'")
        for e in entities:
            if e.get("name") == best_match:
                return e.get("id")

    return None

def search_by_keyword(db_path: str, keyword: str) -> List[Dict[str, Any]]:
    data = _load(db_path)
    results = []
    keyword = keyword.lower().strip()

    for e in data["entities"]:
        searchable_text = f"{e.get('name')} {' '.join(e.get('tags', []))} {e.get('summary')} {e.get('era')}".lower()
        if keyword in searchable_text:
            results.append(e)
    return results

# --- 변경 기능 (Create, Update, Delete) ---

def create_entity(db_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _load(db_path)
    existing_ids = [e.get("id", "") for e in data["entities"]]

    eid = payload.get("id") or _next_id(existing_ids)
    if any(e.get("id") == eid for e in data["entities"]):
        raise ValueError(f"Entity ID already exists: {eid}")

    now = _now_iso()
    payload = dict(payload)
    payload["id"] = eid
    payload.setdefault("created_at", now)
    payload.setdefault("updated_at", now)

    try:
        entity_obj = HistoricalEntity.from_dict(payload)
        final_data = entity_obj.to_dict()
    except Exception as e:
        raise ValueError(f"Invalid entity data: {e}")

    data["entities"].append(final_data)
    _save(db_path, data)
    return final_data

def update_entity(db_path: str, entity_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    data = _load(db_path)
    for i, e in enumerate(data["entities"]):
        if e.get("id") == entity_id:
            updated = dict(e)
            updated.update(patch)
            updated["id"] = entity_id
            updated["updated_at"] = _now_iso()

            if "related_entities" in patch:
                rels = patch["related_entities"]
                updated["related_entities"] = [
                    RelatedEntity(**r).to_dict() if isinstance(r, dict) else r
                    for r in rels
                ]

            data["entities"][i] = updated
            _save(db_path, data)
            return updated

    raise KeyError(f"Entity not found: {entity_id}")

def delete_entity(db_path: str, entity_id: str) -> bool:
    data = _load(db_path)
    before_count = len(data["entities"])

    data["entities"] = [e for e in data["entities"] if e.get("id") != entity_id]

    if len(data["entities"]) == before_count:
        return False

    for e in data["entities"]:
        rels = e.get("related_entities", [])
        if not rels:
            continue
        new_rels = [r for r in rels if r.get("target_id") != entity_id]
        if len(new_rels) != len(rels):
            e["related_entities"] = new_rels
            e["updated_at"] = _now_iso()

    _save(db_path, data)
    return True
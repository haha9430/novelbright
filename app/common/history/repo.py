from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import difflib  # <--- [중요] 이 줄이 꼭 추가되어야 합니다!
import json
import os

from .schema import HistoricalEntity, RelatedEntity
from .storage import read_json, write_json_atomic
from app.common.history.vector_store import vector_store

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

# ---------------------------------------------------------
# [Helper] 벡터 DB 동기화
# ---------------------------------------------------------
def force_sync_vector_db(db_path: str):
    _sync_vector_db(db_path)

def _sync_vector_db(db_path: str):
    """
    현재 JSON DB의 내용을 읽어와 벡터 DB(Chroma)를 갱신합니다.
    Create/Update/Delete 직후에 호출됩니다.
    """
    try:
        current_data = list_entities(db_path)
        vector_store.sync_from_json(current_data)
        print(f"✅ [Repo] 벡터 DB 동기화 완료 (총 {len(current_data)}건)")
    except Exception as e:
        print(f"⚠️ [Repo] 벡터 DB 동기화 실패: {e}")

# ---------------------------------------------------------
# [Read] 조회 및 검색 기능
# ---------------------------------------------------------

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
    special_chars = "·,.-_ []{}()"
    result = str(s).lower()
    for char in special_chars:
        result = result.replace(char, "")
    return result

def find_id_by_name(db_path: str, name: str) -> Optional[str]:
    """
    이름으로 ID 찾기 (4단계 매칭 알고리즘)
    1. 정확 일치 -> 2. 정규화 일치 -> 3. 포함 관계 -> 4. 순서 포함(Subsequence) -> 5. 유사도
    """
    target_raw = (name or "").strip()
    if not target_raw:
        return None

    data = _load(db_path)
    entities = data["entities"]

    # 1. [100%] 정확한 일치
    for e in entities:
        if e.get("name") == target_raw:
            return e.get("id")

    # 정규화 (공백/특수문자 제거)
    target_norm = normalize_string(target_raw)

    # 2. [90%] 정규화 일치 ("홍 릉" == "홍릉")
    for e in entities:
        if normalize_string(e.get("name")) == target_norm:
            return e.get("id")

    # 3. [80%] 포함 관계 ("홍릉" in "홍릉·유릉")
    for e in entities:
        e_norm = normalize_string(e.get("name"))
        if target_norm in e_norm or e_norm in target_norm:
            return e.get("id")

    # 4. [70%] 순서대로 글자가 포함된 경우 (홍유릉 -> 홍릉·유릉)
    for e in entities:
        e_norm = normalize_string(e.get("name"))
        it = iter(e_norm)
        if all(char in it for char in target_norm):
            return e.get("id")

    # 5. [최후의 수단] 유사도 검색 (difflib)
    entity_names = [e.get("name", "") for e in entities]
    matches = difflib.get_close_matches(target_raw, entity_names, n=1, cutoff=0.4)
    if matches:
        best_match = matches[0]
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


# ---------------------------------------------------------
# [Write] 변경 기능 (Create, Update, Delete)
# ---------------------------------------------------------

def create_entity(db_path: str, payload: Dict[str, Any], auto_sync: bool = True) -> Dict[str, Any]:
    data = _load(db_path)
    existing_ids = [e.get("id", "") for e in data["entities"]]

    # ID 생성
    eid = payload.get("id") or _next_id(existing_ids)
    if any(e.get("id") == eid for e in data["entities"]):
        raise ValueError(f"Entity ID already exists: {eid}")

    now = _now_iso()
    payload = dict(payload)
    payload["id"] = eid
    payload.setdefault("created_at", now)
    payload.setdefault("updated_at", now)

    # 객체 검증 및 변환
    try:
        entity_obj = HistoricalEntity.from_dict(payload)
        final_data = entity_obj.to_dict()
    except Exception as e:
        raise ValueError(f"Invalid entity data: {e}")

    # 1. JSON DB 저장
    data["entities"].append(final_data)
    _save(db_path, data)

    # 👇 auto_sync가 True일 때만 동기화 수행
    if auto_sync:
        _sync_vector_db(db_path)

    return final_data

def update_entity(db_path: str, entity_id: str, patch: Dict[str, Any], auto_sync: bool = True) -> Dict[str, Any]:
    data = _load(db_path)
    for i, e in enumerate(data["entities"]):
        if e.get("id") == entity_id:
            updated = dict(e)
            updated.update(patch)
            updated["id"] = entity_id # ID 불변
            updated["updated_at"] = _now_iso()

            if "related_entities" in patch:
                rels = patch["related_entities"]
                updated["related_entities"] = [
                    RelatedEntity(**r).to_dict() if isinstance(r, dict) else r
                    for r in rels
                ]

            # 1. JSON DB 저장
            data["entities"][i] = updated
            _save(db_path, data)

            # 👇 auto_sync가 True일 때만 동기화 수행
            if auto_sync:
                _sync_vector_db(db_path)

            return updated

    raise KeyError(f"Entity not found: {entity_id}")

def delete_entity(db_path: str, entity_id: str, auto_sync: bool = True) -> bool:
    data = _load(db_path)
    before_count = len(data["entities"])

    # 본체 삭제
    data["entities"] = [e for e in data["entities"] if e.get("id") != entity_id]

    if len(data["entities"]) == before_count:
        return False # 삭제된 게 없음

    # 관계 데이터 정리 (Cascade 유사 효과)
    for e in data["entities"]:
        rels = e.get("related_entities", [])
        if not rels:
            continue
        new_rels = [r for r in rels if r.get("target_id") != entity_id]
        if len(new_rels) != len(rels):
            e["related_entities"] = new_rels
            e["updated_at"] = _now_iso()

    # 1. JSON DB 저장
    _save(db_path, data)

    # 👇 auto_sync가 True일 때만 동기화 수행
    if auto_sync:
        _sync_vector_db(db_path)

    return True

def upsert_material(db_path: str, new_material_data: dict):
    """
    ID를 기준으로 기존 데이터가 있으면 교체(Update), 없으면 추가(Insert)
    """
    # 1. 파일 로드 (없으면 빈 리스트 생성)
    # ---------------------------------------------------------
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            all_materials = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_materials = []

    # 2. 탐색: 이미 존재하는 자료인지 ID로 확인
    # ---------------------------------------------------------
    target_idx = -1
    for i, item in enumerate(all_materials):
        if item["id"] == new_material_data["id"]:
            target_idx = i
            break

    # 3. 데이터 무결성 보완
    # ---------------------------------------------------------
    # 만약 기존 데이터가 있는데, 새 데이터에 'linked_entity_ids'가 누락되었다면?
    # 실수로 링크 정보가 날아가는 것을 방지하기 위해 기존 값을 유지하는 로직이 필요할 수 있습니다.
    if target_idx >= 0:
        existing_data = all_materials[target_idx]

        # 새 데이터에 linked_entity_ids가 없으면, 기존 걸 그대로 씁니다.
        if "linked_entity_ids" not in new_material_data:
            new_material_data["linked_entity_ids"] = existing_data.get("linked_entity_ids", [])

        # created_at도 보통은 처음에 만든 날짜를 유지합니다.
        if "created_at" not in new_material_data:
            new_material_data["created_at"] = existing_data.get("created_at")

    # 4. 저장 실행 (Upsert)
    # ---------------------------------------------------------
    if target_idx >= 0:
        # [Update] 교체
        all_materials[target_idx] = new_material_data
        action = "updated"
    else:
        # [Insert] 추가
        all_materials.append(new_material_data)
        action = "created"

    # 5. 파일 쓰기
    # ---------------------------------------------------------
    with open(db_path, "w", encoding="utf-8") as f:
        # ensure_ascii=False: 한글 깨짐 방지
        # indent=4: 사람이 보기 좋게 줄바꿈
        json.dump(all_materials, f, ensure_ascii=False, indent=4)

    print(f"💾 Material {action}: {new_material_data.get('title', 'No Title')}")
    return new_material_data

def get_material(db_path: str, material_id: str) -> Optional[Dict[str, Any]]:
    """
        [기능] material_db.json에서 특정 ID의 자료를 찾아서 반환합니다.
        [리턴] 찾으면 dict 객체, 없으면 None
    """
    # 1. 파일이 존재하는지 먼저 확인 (없으면 찾을 것도 없음)
    if not os.path.exists(db_path):
        return None

    try:
        # 2. 파일 읽기
        with open(db_path, "r", encoding="utf-8") as f:
            materials = json.load(f)

        # 3. 리스트를 순회하며 ID 비교 (Linear Search)
        for item in materials:
            if item.get("id") == material_id:
                return item

        # 4. 끝까지 돌았는데 없으면 None 반환
        return None

    except json.JSONDecodeError:
        # 파일은 있는데 내용이 깨져있거나 빈 파일일 경우
        return None
    except Exception as e:
        print(f"❌ Material 조회 중 오류 발생: {e}")
        return None

def delete_material(db_path: str, material_id: str) -> bool:
    """
    [기능] material_db.json에서 해당 ID의 자료를 제거합니다.
    """
    if not os.path.exists(db_path):
        return False

    try:
        # 1. 로드
        with open(db_path, "r", encoding="utf-8") as f:
            materials = json.load(f)

        # 2. 필터링 (삭제할 ID를 뺀 나머지 리스트 생성)
        # 리스트 컴프리헨션으로 해당 ID가 아닌 것만 남깁니다.
        new_materials = [m for m in materials if m["id"] != material_id]

        # 삭제된 게 없으면(길이가 같으면) False
        if len(materials) == len(new_materials):
            return False

        # 3. 저장
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(new_materials, f, ensure_ascii=False, indent=4)

        print(f"🗑️ Material 삭제 완료: {material_id}")
        return True

    except Exception as e:
        print(f"❌ Material 삭제 중 오류: {e}")
        return False
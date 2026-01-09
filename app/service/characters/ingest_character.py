from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.common.characters import (
    init_db,
    create_character,
    update_character,
    delete_character,
    list_characters,
)
from app.service.characters.solar_client import SolarClient

INPUT_PATH = "app/common/data/character_input.json"
DB_PATH = "app/common/data/characters.json"


def load_input_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "text" not in data:
        raise KeyError(f"Missing key 'text' in {path}")
    return data["text"]


def find_id_by_name(db_path: str, name: str) -> Optional[str]:
    name = (name or "").strip()
    if not name:
        return None
    for c in list_characters(db_path):
        if (c.get("name") or "").strip() == name:
            return c.get("id")
    return None


def _as_str(x: Any) -> str:
    return x if isinstance(x, str) else ("" if x is None else str(x))


def _as_list_str(x: Any) -> list[str]:
    if isinstance(x, list):
        return [(_as_str(v)).strip() for v in x if (_as_str(v)).strip()]
    return []


def normalize_character_payload(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    create에 들어갈 캐릭터 payload 최소 보정.
    (id/created_at/updated_at은 repo가 처리)
    """
    out: Dict[str, Any] = {
        "name": _as_str(d.get("name", "")).strip(),
        "birthdate_or_age": _as_str(d.get("birthdate_or_age", "")).strip(),
        "gender": _as_str(d.get("gender", "")).strip(),
        "occupation": _as_str(d.get("occupation", "")).strip(),
        "core_features": _as_list_str(d.get("core_features", [])),
        "personality_strengths": _as_list_str(d.get("personality_strengths", [])),
        "personality_weaknesses": _as_list_str(d.get("personality_weaknesses", [])),
        "external_goal": _as_str(d.get("external_goal", "")).strip(),
        "internal_goal": _as_str(d.get("internal_goal", "")).strip(),
        "trauma_weakness": _as_str(d.get("trauma_weakness", "")).strip(),
        "speech_habit": _as_str(d.get("speech_habit", "")).strip(),
        "additional_settings": d.get("additional_settings") if isinstance(d.get("additional_settings"), dict) else {},
    }

    # relationships: Solar는 target_name을 줄 수도 있어서, target_id로 변환(임시로 이름을 넣음)
    rels = d.get("relationships", [])
    fixed_rels = []
    if isinstance(rels, list):
        for r in rels:
            if not isinstance(r, dict):
                continue
            target_name = _as_str(r.get("target_name", "")).strip()
            fixed_rels.append({
                "target_id": target_name,  # 지금은 임시로 이름 저장
                "type": _as_str(r.get("type", "")).strip(),
                "summary": _as_str(r.get("summary", "")).strip(),
            })
    out["relationships"] = fixed_rels

    if not out["name"]:
        raise ValueError("create payload missing required field: name")

    return out


def normalize_patch(patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    update에 들어갈 patch 최소 보정.
    - patch는 '변경할 필드만' 들어오는 게 정석
    - 여긴 타입만 가볍게 정리
    """
    if not isinstance(patch, dict):
        return {}

    cleaned: Dict[str, Any] = {}

    # 문자열 필드들
    for k in [
        "name", "birthdate_or_age", "gender", "occupation",
        "external_goal", "internal_goal", "trauma_weakness", "speech_habit"
    ]:
        if k in patch:
            cleaned[k] = _as_str(patch.get(k)).strip()

    # 리스트 필드들
    for k in ["core_features", "personality_strengths", "personality_weaknesses"]:
        if k in patch:
            cleaned[k] = _as_list_str(patch.get(k))

    # additional_settings
    if "additional_settings" in patch and isinstance(patch.get("additional_settings"), dict):
        cleaned["additional_settings"] = patch["additional_settings"]

    # relationships (선택)
    if "relationships" in patch:
        rels = patch.get("relationships", [])
        fixed_rels = []
        if isinstance(rels, list):
            for r in rels:
                if not isinstance(r, dict):
                    continue
                # update에서도 target_name을 받으면 target_id로 바꿔 저장
                target_name = _as_str(r.get("target_name", "")).strip()
                target_id = _as_str(r.get("target_id", "")).strip()
                fixed_rels.append({
                    "target_id": target_id or target_name,
                    "type": _as_str(r.get("type", "")).strip(),
                    "summary": _as_str(r.get("summary", "")).strip(),
                })
        cleaned["relationships"] = fixed_rels

    return cleaned


def normalize_command(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """
    Solar가 반환한 명령 JSON(action/target/payload/patch)을 안정적으로 정리.
    기대 형태:
    {
      "action": "create|update|delete",
      "target": {"id": "...", "name": "..."},
      "payload": {...},   # create일 때
      "patch": {...}      # update일 때
    }
    """
    if not isinstance(cmd, dict):
        raise ValueError("AI command is not a dict")

    action = _as_str(cmd.get("action", "")).strip().lower()
    if action not in {"create", "update", "delete"}:
        # 혹시 Solar가 create/update/delete 말고 다른 단어를 쓰면 여기서 막음
        raise ValueError(f"Invalid action from AI: {action}")

    target = cmd.get("target") if isinstance(cmd.get("target"), dict) else {}
    target_id = _as_str(target.get("id", "")).strip() or None
    target_name = _as_str(target.get("name", "")).strip() or None

    payload = cmd.get("payload") if isinstance(cmd.get("payload"), dict) else {}
    patch = cmd.get("patch") if isinstance(cmd.get("patch"), dict) else {}

    return {
        "action": action,
        "target": {"id": target_id, "name": target_name},
        "payload": payload,
        "patch": patch,
    }


def apply_command(db_path: str, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """
    정리된 command를 실제 repo 호출로 반영.
    """
    init_db(db_path)

    action = cmd["action"]
    target_id = cmd["target"]["id"]
    target_name = cmd["target"]["name"]

    if action == "create":
        payload = normalize_character_payload(cmd["payload"])
        saved = create_character(db_path, payload)
        return {"status": "created", "character": saved}

    if action == "update":
        if not target_id and target_name:
            target_id = find_id_by_name(db_path, target_name)
        if not target_id:
            return {"status": "failed", "error": "update target not found (provide id or existing name)"}

        patch = normalize_patch(cmd["patch"])
        if not patch:
            return {"status": "failed", "error": "empty patch for update"}

        updated = update_character(db_path, target_id, patch)
        return {"status": "updated", "character": updated}

    if action == "delete":
        if not target_id and target_name:
            target_id = find_id_by_name(db_path, target_name)
        if not target_id:
            return {"status": "failed", "error": "delete target not found (provide id or existing name)"}

        ok = delete_character(db_path, target_id)
        return {"status": "deleted" if ok else "not_found", "id": target_id}

    return {"status": "failed", "error": f"unknown action: {action}"}


def main() -> None:
    # 1) 입력 읽기
    text = load_input_text(INPUT_PATH)

    # 2) Solar로 "명령" 생성 (create/update/delete + target + payload/patch)
    client = SolarClient()
    ai_cmd_raw = client.parse_command(text)  # ✅ solar_client에서 parse_command를 만들어야 함

    # 3) 명령 정리
    cmd = normalize_command(ai_cmd_raw)

    # 4) DB 반영
    result = apply_command(DB_PATH, cmd)

    print("✅ Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

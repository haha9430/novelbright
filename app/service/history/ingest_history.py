# app/service/history/ingest_history.py
from __future__ import annotations
from typing import Any, Dict, Optional
import json
import os

# (주의) repo 모듈은 common/history/repo.py에 구현되어야 함
from app.common.history import repo
from app.service.history.solar_client import HistoryLLMClient

# 파일 경로 상수 정의
DB_PATH = "app/common/data/history_db.json"
INPUT_PATH = "app/common/data/history_db_input.json"  # 입력 파일 경로

def load_input_text(path: str) -> str:
    """
    JSON 파일에서 'text' 필드의 내용을 읽어옵니다.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "text" not in data:
        raise KeyError(f"파일에 'text' 키가 없습니다: {path}")

    return data["text"]

def normalize_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM이 만든 payload를 스키마에 맞게 안전하게 변환
    """
    return {
        "name": str(raw.get("name", "")).strip(),
        "entity_type": str(raw.get("entity_type", "Unknown")).strip(),
        "era": str(raw.get("era", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
        "description": str(raw.get("description", "")).strip(),
        "tags": [str(t).strip() for t in raw.get("tags", [])],
        "related_entities": raw.get("related_entities", [])
    }

def process_history_text(text: str) -> Dict[str, Any]:
    """
    1. 텍스트 -> LLM 분석 -> Command(JSON)
    2. Command -> DB 반영
    """
    print(f"🔄 처리 중... (입력 길이: {len(text)}자)")

    # 1. LLM 분석
    client = HistoryLLMClient()
    cmd = client.parse_history_command(text)

    action = cmd.get("action")
    target_name = cmd.get("target", {}).get("name")
    target_id = cmd.get("target", {}).get("id")

    repo.init_db(DB_PATH) # DB 파일 없으면 생성

    # 2. Action 수행
    if action == "create":
        payload = normalize_payload(cmd.get("payload", {}))
        saved_entity = repo.create_entity(DB_PATH, payload)
        return {"status": "created", "data": saved_entity}

    elif action == "update":
        if not target_id and target_name:
            found_id = repo.find_id_by_name(DB_PATH, target_name)
            if found_id:
                target_id = found_id

        if not target_id:
            return {"status": "error", "message": f"수정할 대상을 찾을 수 없습니다: {target_name}"}

        patch = cmd.get("patch", {})
        updated_entity = repo.update_entity(DB_PATH, target_id, patch)
        return {"status": "updated", "data": updated_entity}

    elif action == "delete":
        print(f"DEBUG: 삭제 시도 대상 이름 = [{target_name}]")
        if not target_id and target_name:
            target_id = repo.find_id_by_name(DB_PATH, target_name)

        if target_id and repo.delete_entity(DB_PATH, target_id):
            return {"status": "deleted", "id": target_id}
        else:
            return {"status": "error", "message": "삭제 실패 (대상을 찾을 수 없음)"}

    return {"status": "unknown_action", "action": action}

# --- 메인 실행부 ---
if __name__ == "__main__":
    try:
        # 1. 파일에서 텍스트 읽기
        print(f"📂 입력 파일 읽는 중: {INPUT_PATH}")
        input_text = load_input_text(INPUT_PATH)

        # 2. 처리 실행
        result = process_history_text(input_text)

        # 3. 결과 출력
        print("\n✅ [처리 결과]:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n📁 DB 저장 완료: {DB_PATH}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
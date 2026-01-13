# app/service/clio_fact_checker_agent/history_router.py

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

# Common 모듈 import
from app.common.history import repo as history_repo
from app.common.history import vector_store

# Schemas (필요한 경우 common schemas를 쓰거나 현재 패키지의 schemas 사용)
from .schemas import HistoryOut, HistoryCreate, HistoryUpdate, IngestRequest

from app.service.history.solar_client import HistoryLLMClient

router = APIRouter(prefix="/history", tags=["History Manager"])

HISTORY_DB_PATH = "app/data/history_db.json" # 경로 확인 필요

from pydantic import BaseModel

class HistoryRewriteRequest(BaseModel):
    entity_ids: List[str]  # 삭제할 기존 ID 목록
    text: str              # 새로 분석하여 넣을 텍스트

class DeleteRequest(BaseModel):
    entity_ids: List[str]

# ---------------------------------------------------------
# Helper Functions (내부 함수)
# ---------------------------------------------------------
def _normalize_ingest_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    # ... (기존 코드 그대로 복사) ...
    return {
        "name": str(raw_payload.get("name", "")).strip(),
        # ... 생략 ...
    }

def _merge_entity_data(existing: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    # ... (기존 코드 그대로 복사) ...
    merged = existing.copy()
    # ... 생략 ...
    return merged

# ---------------------------------------------------------
# API Endpoints (app.get -> router.get 으로 변경됨!)
# ---------------------------------------------------------

@router.get("", response_model=List[HistoryOut])
def api_list_history_entities():
    """전체 역사 엔티티 목록 조회"""
    return history_repo.list_entities(HISTORY_DB_PATH)

@router.get("/search", response_model=List[HistoryOut])
def api_search_history(q: str = Query(..., description="검색할 키워드")):
    """벡터 검색"""
    results = vector_store.search(q, top_k=5)
    response_list = []
    for doc, score in results:
        # 벡터 DB에는 요약된 텍스트만 있으므로,
        # 필요하다면 ID를 가지고 repo.get_entity()로 원본 상세 데이터를 다시 가져와도 됩니다.
        # 여기서는 메타데이터를 활용해 반환합니다.
        entity_id = doc.metadata["id"]
        # 원본 데이터 조회 (가장 확실한 방법)
        original_data = history_repo.get_entity(HISTORY_DB_PATH, entity_id)
        if original_data:
            response_list.append(original_data)
    return response_list


@router.post("", response_model=HistoryOut, tags=["History"])
def api_create_history_entity(payload: HistoryCreate):
    """새로운 역사 엔티티 생성"""
    try:
        # Pydantic 모델 -> Dict 변환 후 repo 전달
        return history_repo.create_entity(HISTORY_DB_PATH, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{entity_id}", response_model=HistoryOut, tags=["History"])
def api_get_history_entity(entity_id: str):
    """ID로 상세 조회"""
    entity = history_repo.get_entity(HISTORY_DB_PATH, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
    return entity

@router.post("/rewrite", tags=["History"])
def api_update_history_entity(payload: HistoryRewriteRequest):
    """
    [일괄 재작성] 지정된 엔티티들을 삭제하고, 입력된 텍스트를 분석하여 새로 생성합니다.
    - 단계 1: entity_ids에 있는 항목 제거
    - 단계 2: text를 LLM으로 분석하여 Ingest (Create/Update/Delete 수행)
    - 단계 3: 벡터 DB 일괄 동기화 (마지막에 1회)
    """
    target_ids = payload.entity_ids
    input_text = payload.text

    print(f"🔄 [API/Rewrite] 재작성 요청: 삭제 {len(target_ids)}건, 분석 텍스트 {len(input_text)}자")

    results = []
    success_count = 0

    # ---------------------------------------------------------
    # 1. [DELETE] 기존 엔티티 일괄 삭제
    # ---------------------------------------------------------
    for ent_id in target_ids:
        try:
            # auto_sync=False: 속도를 위해 벡터 동기화는 나중에 한 번에 함
            history_repo.delete_entity(HISTORY_DB_PATH, ent_id, auto_sync=False)
            print(f"   🗑️ 삭제 완료: {ent_id}")
            results.append({
                "action": "pre_delete",
                "id": ent_id,
                "status": "success",
                "message": "재작성 전 삭제됨"
            })
        except Exception as e:
            # 이미 없는 경우 등 에러가 나도, 재생성 로직은 계속 진행해야 함
            print(f"   ⚠️ 삭제 중 오류 (무시함): {ent_id} - {e}")

    # ---------------------------------------------------------
    # 2. [INGEST] 텍스트 분석 및 반영 (기존 ingest 로직 재사용)
    # ---------------------------------------------------------
    client = HistoryLLMClient()
    try:
        commands = client.parse_history_command(input_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")

    if commands:
        for cmd in commands:
            suggested_action = cmd.get("action", "create")
            target_name = cmd.get("target", {}).get("name")

            # DB에서 이름으로 ID 검색
            existing_id = history_repo.find_id_by_name(HISTORY_DB_PATH, target_name)

            final_action = suggested_action
            final_target_id = existing_id

            # Ingest 특유의 Upsert 로직 (Create인데 이미 있으면 Update로 변경)
            if suggested_action == "create" and existing_id:
                final_action = "update"

            log_item = {"name": target_name, "action": final_action, "status": "pending"}

            try:
                raw_payload = cmd.get("payload", {})
                normalized_payload = _normalize_ingest_payload(raw_payload)

                if final_action == "create":
                    # auto_sync=False 유지
                    saved_entity = history_repo.create_entity(HISTORY_DB_PATH, normalized_payload, auto_sync=False)

                    log_item.update({
                        "status": "success",
                        "id": saved_entity["id"],
                        "message": "새로 생성됨",
                        "result_data": saved_entity
                    })
                    success_count += 1

                elif final_action == "update":
                    if not final_target_id:
                        # 혹시 모를 예외 처리 (Update인데 ID가 없는 경우)
                        raise ValueError(f"업데이트 대상 ID 없음: {target_name}")

                    existing_entity = history_repo.get_entity(HISTORY_DB_PATH, final_target_id)
                    merged_data = _merge_entity_data(existing_entity, normalized_payload)

                    updated_entity = history_repo.update_entity(HISTORY_DB_PATH, final_target_id, merged_data, auto_sync=False)

                    log_item.update({
                        "status": "success",
                        "id": updated_entity["id"],
                        "message": "기존 정보에 병합됨",
                        "result_data": updated_entity
                    })
                    success_count += 1

                elif final_action == "delete":
                    if final_target_id:
                        history_repo.delete_entity(HISTORY_DB_PATH, final_target_id, auto_sync=False)
                        log_item.update({"status": "success", "id": final_target_id, "message": "분석 결과에 따라 삭제됨"})
                        success_count += 1

            except Exception as e:
                log_item.update({"status": "error", "message": str(e)})
                print(f"⚠️ Ingest 처리 실패 ({target_name}): {e}")

            results.append(log_item)

    # ---------------------------------------------------------
    # 3. [SYNC] 벡터 DB 일괄 동기화
    # ---------------------------------------------------------
    # 삭제된 항목과 새로 생성된 항목을 모두 반영하기 위해 Force Sync 수행
    print("🔄 [API/Rewrite] 모든 변경사항 벡터 DB 동기화 중...")
    try:
        history_repo.force_sync_vector_db(HISTORY_DB_PATH)
    except Exception as e:
        print(f"⚠️ 벡터 DB 동기화 실패: {e}")
        # 벡터 동기화 실패는 전체 실패로 간주하지 않고 결과 반환 (필요시 수정)

    return {
        "status": "success",
        "message": f"재작성 완료 (삭제 요청 {len(target_ids)}건, 신규 처리 {success_count}건)",
        "details": results
    }

@router.post("/delete", tags=["History"])
def api_delete_history_entity(payload: DeleteRequest):
    """엔티티 삭제"""
    target_ids = payload.entity_ids
    print(target_ids)

    print(f"🔄 [API/Rewrite] 삭제 요청: 삭제 {len(target_ids)}건")

    results = []

    # ---------------------------------------------------------
    # 1. [DELETE] 기존 엔티티 일괄 삭제
    # ---------------------------------------------------------
    for ent_id in target_ids:
        try:
            # auto_sync=False: 속도를 위해 벡터 동기화는 나중에 한 번에 함
            history_repo.delete_entity(HISTORY_DB_PATH, ent_id, auto_sync=False)
            print(f"   🗑️ 삭제 완료: {ent_id}")
            results.append({
                "action": "pre_delete",
                "id": ent_id,
                "status": "success",
                "message": "삭제됨"
            })
        except Exception as e:
            # 이미 없는 경우 등 에러가 나도, 재생성 로직은 계속 진행해야 함
            print(f"   ⚠️ 삭제 중 오류 (무시함): {ent_id} - {e}")

    # 삭제된 항목과 새로 생성된 항목을 모두 반영하기 위해 Force Sync 수행
    print("🔄 [API/Rewrite] 모든 변경사항 벡터 DB 동기화 중...")
    try:
        history_repo.force_sync_vector_db(HISTORY_DB_PATH)
    except Exception as e:
        print(f"⚠️ 벡터 DB 동기화 실패: {e}")
        # 벡터 동기화 실패는 전체 실패로 간주하지 않고 결과 반환 (필요시 수정)

    return {
        "status": "success",
        "message": f"삭제 완료 (삭제 요청 {len(target_ids)}건)",
        "details": results
    }

@router.post("/ingest", tags=["History"])
def api_ingest_history_text(payload: IngestRequest):
    """
    텍스트를 분석하여 DB에 반영합니다. (Upsert: 이미 있으면 수정, 없으면 생성)
    배치 처리를 위해 벡터 DB 동기화는 맨 마지막에 한 번만 수행합니다.
    """
    input_text = payload.text
    print(f"🔄 [API] 텍스트 분석 및 병합 시도 ({len(input_text)}자)...")

    client = HistoryLLMClient()
    try:
        commands = client.parse_history_command(input_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")

    if not commands:
        return {"summary": "처리된 항목 없음", "details": []}

    results = []
    success_count = 0

    # 1. 반복문 시작
    for cmd in commands:
        suggested_action = cmd.get("action", "create")
        target_name = cmd.get("target", {}).get("name")

        # DB에서 동명이인 검색
        existing_id = history_repo.find_id_by_name(HISTORY_DB_PATH, target_name)

        final_action = suggested_action
        final_target_id = existing_id

        # Upsert 로직: create인데 이미 있으면 update로 변경
        if suggested_action == "create" and existing_id:
            final_action = "update"
            print(f"ℹ️ 중복 발견: '{target_name}'(ID:{existing_id}) -> 'Create'를 'Update'로 전환합니다.")

        log_item = {"name": target_name, "action": final_action, "status": "pending"}

        try:
            raw_payload = cmd.get("payload", {})
            normalized_payload = _normalize_ingest_payload(raw_payload)

            if final_action == "create":
                # [중요] auto_sync=False로 설정하여 매번 동기화 방지
                saved_entity = history_repo.create_entity(HISTORY_DB_PATH, normalized_payload, auto_sync=False)

                log_item.update({
                    "status": "success",
                    "id": saved_entity["id"],
                    "message": "새로 생성됨",
                    "result_data": saved_entity
                })
                success_count += 1

            elif final_action == "update":
                if not final_target_id:
                    raise ValueError(f"수정할 대상 ID를 찾지 못함: {target_name}")

                # 기존 데이터 조회
                existing_entity = history_repo.get_entity(HISTORY_DB_PATH, final_target_id)
                if not existing_entity:
                    raise ValueError("ID는 찾았으나 실제 데이터가 없습니다.")

                # [수정됨] 병합(Merge)을 먼저 수행해야 함!
                merged_data = _merge_entity_data(existing_entity, normalized_payload)

                # 업데이트 수행 (auto_sync=False)
                updated_entity = history_repo.update_entity(HISTORY_DB_PATH, final_target_id, merged_data, auto_sync=False)

                log_item.update({
                    "status": "success",
                    "id": updated_entity["id"],
                    "message": "기존 정보에 병합됨",
                    "result_data": updated_entity
                })
                success_count += 1

            elif final_action == "delete":
                if final_target_id:
                    history_repo.delete_entity(HISTORY_DB_PATH, final_target_id, auto_sync=False)
                    log_item.update({"status": "success", "id": final_target_id, "message": "삭제됨"})
                    success_count += 1
                else:
                    raise ValueError(f"삭제할 대상을 찾을 수 없음: {target_name}")

        except Exception as e:
            log_item.update({"status": "error", "message": str(e)})
            print(f"⚠️ 처리 실패 ({target_name}): {e}")

        # [중요] 처리 결과 기록은 반복문 안에서!
        results.append(log_item)

    # 2. 반복문 종료 후 일괄 동기화 (들여쓰기 주의!)
    if success_count > 0:
        print("🔄 [API] 일괄 변경 완료. 벡터 DB 동기화를 수행합니다...")
        try:
            history_repo.force_sync_vector_db(HISTORY_DB_PATH)
        except Exception as e:
            print(f"⚠️ 벡터 DB 동기화 중 오류 발생: {e}")

    # 3. 최종 반환 (들여쓰기 주의!)
    return {
        "summary": f"총 {len(commands)}건 중 {success_count}건 처리 완료",
        "details": results
    }
# app/service/story_keeper_agent/api.py
import sys
import os
import json
import inspect
from pathlib import Path

sys.path.insert(0, os.getcwd())

from fastapi import APIRouter, HTTPException, Body, Form, Query
from pydantic import ValidationError, BaseModel
from typing import Any, Dict

from app.service.story_keeper_agent.ingest_episode import (
    ingest_episode,
    IngestEpisodeRequest,
)
from app.service.story_keeper_agent.ingest_episode.chunking import split_into_chunks
from app.service.story_keeper_agent.load_state.extracter import PlotManager

from app.service.story_keeper_agent.rules.check_consistency import check_consistency
from app.service.characters import upsert_character

router = APIRouter(prefix="/story", tags=["story-keeper"])
manager = PlotManager()


def _project_root() -> Path:
    # extracter.py랑 동일한 기준(루트 기준)으로 맞춤
    return Path(__file__).resolve().parents[3]


def _data_path(filename: str) -> str:
    return str(_project_root() / "app" / "data" / filename)


def _safe_read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_plot_config() -> dict:
    path = _data_path("plot.json")
    return _safe_read_json(path)


def _extract_world_from_plot(plot_config: dict) -> dict:
    if not isinstance(plot_config, dict):
        return {}
    for k in ("world", "world_setting", "worldSettings", "settings", "setting", "global"):
        v = plot_config.get(k)
        if isinstance(v, dict) and v:
            return v
    return plot_config if isinstance(plot_config, dict) else {}


def _load_story_history() -> dict:
    path = _data_path("story_history.json")
    return _safe_read_json(path)


def _load_character_config() -> dict:
    path = _data_path("characters.json")
    if not os.path.exists(path):
        return {"characters": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"characters": []}

    if isinstance(data, dict):
        chars = []
        for name, d in data.items():
            if isinstance(d, dict):
                x = dict(d)
                x.setdefault("name", name)
                chars.append(x)
        return {"characters": chars}

    if isinstance(data, list):
        chars = [d for d in data if isinstance(d, dict) and d.get("name")]
        return {"characters": chars}

    return {"characters": []}


def _call_upsert_character(name: str, text: str):
    print(f"📂 현재 실행 위치(CWD): {os.getcwd()}")
    target_path = os.path.abspath(_data_path("characters.json"))
    print(f"💾 실제 저장 시도 경로: {target_path}")

    try:
        result = upsert_character(
            name=name,
            features=text,
            db_path=target_path
        )

        if result.get("status") == "success":
            print(f"✅ 저장 성공! 저장된 키(Key): {result.get('name')}")
            print(f"   👉 행동: {result.get('action')}")
        else:
            print(f"❌ 저장 실패 응답: {result}")

        return result
    except TypeError:
        return upsert_character(name, text)
    except Exception:
        raise


@router.get(
    "/history",
    summary="Story History",
    description="app/data/story_history.json을 그대로 반환",
)
def get_story_history():
    try:
        history = _load_story_history()
        if not isinstance(history, dict):
            history = {}
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"history load failed: {e}")


@router.post(
    "/world_setting",
    summary="World/Plot Setting",
    description="설정 입력 -> plot.json 갱신(PlotManager 내부 저장)",
)
def world_setting(text: str = Body(..., media_type="text/plain")):
    return manager.update_global_settings(text)


# ✅ 추가: 파일 업로드(텍스트) ingest 엔드포인트
class IngestRequest(BaseModel):
    text: str
    type: str  # "world" / "worldview" / etc


@router.post(
    "/ingest",
    summary="Ingest Text",
    description="프론트에서 변환된 텍스트를 받아 type에 따라 저장/요약 처리",
)
def ingest(payload: IngestRequest):
    try:
        text = (payload.text or "").strip()
        upload_type = (payload.type or "").strip().lower()

        if not text:
            return {"status": "error", "message": "empty text"}

        # 세계관/설정 파일 업로드 케이스
        if upload_type in ("world", "worldview"):
            # 여기서 요약+plot.json 저장이 update_global_settings 내부에서 이뤄져야 함
            # (너가 extracter에서 만든 '요약해서 plot.json 저장' 로직이 여기로 연결되는 구조)
            res = manager.update_global_settings(text)
            return {"status": "success", "message": "world ingested", "data": res}

        return {"status": "error", "message": f"unsupported type: {upload_type}"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/character_setting",
    summary="Character Setting",
    description="캐릭터 설정 입력 -> 캐릭터 DB 업데이트",
)
def character_setting(name: str = Form(...), text: str = Form(...)):
    try:
        return _call_upsert_character(name=name, text=text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/manuscript_feedback",
    summary="Manuscript Feedback",
    description="원고 업로드 -> plot.json/characters.json/story_history.json과 비교 피드백",
)
def manuscript_feedback(
    episode_no: int,
    text: str = Body(..., media_type="text/plain"),
    debug_raw: bool = Query(False, description="디버그 정보를 포함할지"),
):
    try:
        full_text_str = text or ""
        if not full_text_str.strip():
            raise ValueError("원고가 비어있습니다.")

        plot_config = _load_plot_config()
        world = _extract_world_from_plot(plot_config)

        history = _load_story_history()
        character_config = _load_character_config()
        story_state = {"world": world, "history": history}

        chunks = split_into_chunks(full_text_str)

        ingest_episode(req=IngestEpisodeRequest(episode_no=episode_no, text_chunks=chunks))

        history_after = _load_story_history()
        story_state = {"world": world, "history": history_after}

        episode_facts = manager.extract_facts(episode_no, full_text_str, story_state)
        if isinstance(episode_facts, dict):
            episode_facts["raw_text"] = full_text_str
        else:
            episode_facts = {"raw_text": full_text_str}

        issues = check_consistency(
            episode_facts=episode_facts,
            character_config=character_config,
            plot_config=plot_config,
            story_state=story_state,
        )

        if not issues:
            base = {"episode_no": episode_no, "message": "수정할 사안이 없습니다!", "issues": []}
        else:
            base = {"episode_no": episode_no, "issues": issues}

        if debug_raw:
            base["debug"] = {
                "cwd": os.getcwd(),
                "history_path": _data_path("story_history.json"),
                "full_text_len": len(full_text_str),
                "plot_loaded": bool(plot_config),
                "world_loaded": bool(world),
                "history_loaded": bool(history_after),
                "character_count": len(character_config.get("characters", [])) if isinstance(character_config, dict) else 0,
                "issues_count": len(issues) if isinstance(issues, list) else 0,
            }

        return base

    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

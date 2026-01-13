# app/service/story_keeper_agent/api.py
import sys
import os
import json

sys.path.insert(0, os.getcwd())

from fastapi import APIRouter, HTTPException, Body, Form
from pydantic import ValidationError

from app.service.story_keeper_agent.ingest_episode import (
    ingest_episode,
    IngestEpisodeRequest,
)
from app.service.story_keeper_agent.ingest_episode.chunking import split_into_chunks
from app.service.story_keeper_agent.load_state.extracter import PlotManager

from app.service.story_keeper_agent.rules.check_consistency import check_consistency
from app.service.story_keeper_agent.finalize_episode import issues_to_edits

from app.service.characters import upsert_character

router = APIRouter(prefix="/story", tags=["story-keeper"])
manager = PlotManager()


def _extract_text_from_response(res):
    if isinstance(res, dict):
        return res.get("full_text") or res.get("content") or res.get("text") or res.get("body") or ""
    if hasattr(res, "full_text"):
        return res.full_text
    if hasattr(res, "content"):
        return res.content
    if hasattr(res, "text"):
        return res.text
    if hasattr(res, "body"):
        return res.body
    return str(res)


def _load_plot_world() -> dict:
    here = os.getcwd()
    p1 = os.path.join(here, "app", "data", "plot.json")

    if os.path.exists(p1):
        with open(p1, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    try:
        world = manager._read_json(manager.global_setting_file, default={})
        return world if isinstance(world, dict) else {}
    except Exception:
        return {}


def _load_story_history() -> dict:
    try:
        data = manager._read_json(manager.history_file, default={})
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_character_config() -> dict:
    here = os.getcwd()
    path = os.path.join(here, "app", "data", "characters.json")
    if not os.path.exists(path):
        return {"characters": []}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

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


# =========================
# 1) World Setting
# =========================
@router.post(
    "/world_setting",
    summary="World Setting",
    description="세계관/설정 입력 -> 저장",
)
def world_setting(text: str = Body(..., media_type="text/plain")):
    return manager.update_global_settings(text)


# =========================
# 2) Character Setting (✅ 입력칸 2개로 뜨게)
# =========================
@router.post(
    "/character_setting",
    summary="Character Setting",
    description="이름(key) + 특징(설명) 2칸 입력 -> characters.json에 upsert",
)
def character_setting(
    name: str = Form(..., description="캐릭터 이름(키값)"),
    features: str = Form(..., description="캐릭터 특징/설명(서술/양식 아무거나)"),
):
    try:
        return upsert_character(name, features)
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# 3) Manuscript Feedback
# =========================
@router.post(
    "/manuscript_feedback",
    summary="Manuscript Feedback",
    description="원고(회차) 입력 -> 청크 -> 저장/상태 로드 -> 규칙 검사 -> 수정안 반환",
)
def manuscript_feedback(
    episode_no: int,
    raw_text: str = Body(..., media_type="text/plain"),
):
    try:
        chunks = split_into_chunks(raw_text, max_len=2500, min_len=1500)

        try:
            req = IngestEpisodeRequest(episode_no=episode_no, chunks=chunks)
        except ValidationError:
            req = IngestEpisodeRequest(episode_no=episode_no, text_chunks=chunks)

        res = ingest_episode(req)
        full_text_str = _extract_text_from_response(res)

        manager.summarize_and_save(episode_no, full_text_str)

        world = _load_plot_world()
        history = _load_story_history()
        story_state = {"world": world, "history": history}

        character_config = _load_character_config()

        episode_facts = manager.extract_facts(episode_no, full_text_str, story_state)

        if isinstance(episode_facts, dict):
            episode_facts["raw_text"] = full_text_str
        else:
            episode_facts = {"raw_text": full_text_str}

        plot_config = {}

        issues = check_consistency(
            episode_facts=episode_facts,
            character_config=character_config,
            plot_config=plot_config,
            story_state=story_state,
        )

        edits = issues_to_edits(
            issues,
            episode_no=episode_no,
            raw_text=full_text_str,
        )

        return {
            "episode_no": episode_no,
            "edits": edits,
            "debug": {
                "issue_count": len(edits),
                "full_text_len": len(full_text_str or ""),
                "world_loaded": bool(world),
                "history_count": len(history) if isinstance(history, dict) else 0,
                "character_count": len(character_config.get("characters", []))
                if isinstance(character_config, dict)
                else 0,
            },
        }

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

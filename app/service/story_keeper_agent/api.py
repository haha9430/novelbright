import sys
import os
import json

sys.path.insert(0, os.getcwd())

from fastapi import APIRouter, HTTPException, Body
from pydantic import ValidationError

from app.service.story_keeper_agent.ingest_episode import (
    ingest_episode,
    IngestEpisodeRequest,
)
from app.service.story_keeper_agent.ingest_episode.chunking import split_into_chunks
from app.service.story_keeper_agent.load_state.extracter import PlotManager

from app.service.story_keeper_agent.rules.check_consistency import check_consistency
from app.service.story_keeper_agent.finalize_episode import issues_to_edits

# ✅ story_keeper_main.py가 이 변수를 import해야 하니까 "router" 이름 고정!
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
    """
    plot.json(세계관 설정) 로드: app/data/plot.json 우선, 없으면 PlotManager 경로 사용
    """
    here = os.getcwd()
    p1 = os.path.join(here, "app", "data", "plot.json")

    if os.path.exists(p1):
        with open(p1, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    # fallback (기존 manager 경로)
    try:
        world = manager._read_json(manager.global_setting_file, default={})
        return world if isinstance(world, dict) else {}
    except Exception:
        return {}


def _load_story_history() -> dict:
    """
    story_history.json 로드: load_state 폴더에 저장되는 파일
    """
    try:
        data = manager._read_json(manager.history_file, default={})
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_character_config() -> dict:
    """
    캐릭터 설정: app/data/characters.json
    - {"characters":[...]} or {"profiles":{...}} or {"이름":{...}} or [{"name":...}]
    => {"characters":[...]}로 정규화
    """
    here = os.getcwd()
    path = os.path.join(here, "app", "data", "characters.json")
    if not os.path.exists(path):
        return {"characters": []}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and isinstance(data.get("characters"), list):
        return {"characters": data["characters"]}

    if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
        chars = []
        for name, d in data["profiles"].items():
            if isinstance(d, dict):
                x = dict(d)
                x.setdefault("name", name)
                chars.append(x)
        return {"characters": chars}

    if isinstance(data, dict):
        chars = []
        for name, d in data.items():
            if isinstance(d, dict):
                x = dict(d)
                x.setdefault("name", name)
                chars.append(x)
        return {"characters": chars}

    if isinstance(data, list):
        chars = []
        for d in data:
            if isinstance(d, dict) and d.get("name"):
                chars.append(d)
        return {"characters": chars}

    return {"characters": []}


@router.post("/setting")
def update_setting(text: str = Body(..., media_type="text/plain")):
    # plot.json에는 세계관만 저장하도록 PlotManager쪽 로직을 맞춘 상태라고 가정
    return manager.update_global_settings(text)


@router.post("/ingest_plain")
def ingest_plain(
    episode_no: int,
    raw_text: str = Body(..., media_type="text/plain"),
):
    try:
        # 1) 청크 자르기
        chunks = split_into_chunks(raw_text, max_len=2500, min_len=1500)

        # 2) Request 생성(스키마 호환)
        try:
            req = IngestEpisodeRequest(episode_no=episode_no, chunks=chunks)
        except ValidationError:
            req = IngestEpisodeRequest(episode_no=episode_no, text_chunks=chunks)

        # 3) ingest → full_text
        res = ingest_episode(req)
        full_text_str = _extract_text_from_response(res)

        # 4) story_history 저장(요약 중심)
        manager.summarize_and_save(episode_no, full_text_str)

        # 5) story_state 구성: plot.json(world) + story_history
        world = _load_plot_world()
        history = _load_story_history()
        story_state = {"world": world, "history": history}

        # 6) 캐릭터 config
        character_config = _load_character_config()

        # 7) facts 추출
        episode_facts = manager.extract_facts(episode_no, full_text_str, story_state)

        # ✅ 핵심: rules에서 원고를 읽을 수 있도록 raw_text 강제 주입
        if isinstance(episode_facts, dict):
            episode_facts["raw_text"] = full_text_str
        else:
            episode_facts = {"raw_text": full_text_str}

        # 8) plot_config는 비워두거나(향후 확장)
        plot_config = {}

        # 9) 규칙 체크
        issues = check_consistency(
            episode_facts=episode_facts,
            character_config=character_config,
            plot_config=plot_config,
            story_state=story_state,
        )

        # 10) issues → edits
        edits = issues_to_edits(issues)

        # ✅ 응답은 수정 피드백만
        return {
            "episode_no": episode_no,
            "edits": edits,
            "debug": {
                "issue_count": len(edits),
                "full_text_len": len(full_text_str or ""),
                "has_raw_text": True,
                "world_loaded": bool(world),
                "history_count": len(history) if isinstance(history, dict) else 0,
                "character_count": len(character_config.get("characters", [])) if isinstance(character_config, dict) else 0,
            },
        }

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

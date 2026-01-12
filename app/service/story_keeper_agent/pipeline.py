from __future__ import annotations

import os
import json
from typing import Any, Dict

from pydantic import ValidationError

from app.service.story_keeper_agent.ingest_episode import ingest_episode, IngestEpisodeRequest
from app.service.story_keeper_agent.ingest_episode.chunking import split_into_chunks
from app.service.story_keeper_agent.load_state.extracter import PlotManager
from app.service.story_keeper_agent.rules.check_consistency import check_consistency
from app.service.story_keeper_agent.finalize_episode import finalize_episode


def _load_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_world_state() -> Dict[str, Any]:
    path = os.path.join(os.getcwd(), "app", "data", "plot.json")
    data = _load_json(path, default={})
    return data if isinstance(data, dict) else {}


def _load_character_config() -> Dict[str, Any]:
    path = os.path.join(os.getcwd(), "app", "data", "characters.json")
    data = _load_json(path, default={})
    return data if isinstance(data, dict) else {"characters": []}


def run_pipeline(episode_no: int, raw_text: str) -> Dict[str, Any]:
    manager = PlotManager()

    # 1) chunking
    chunks = split_into_chunks(raw_text, max_len=2500, min_len=1500)

    # 2) ingest
    try:
        req = IngestEpisodeRequest(episode_no=episode_no, chunks=chunks)
    except ValidationError:
        req = IngestEpisodeRequest(episode_no=episode_no, text_chunks=chunks)

    res = ingest_episode(req)
    full_text = getattr(res, "full_text", None) or (res.get("full_text") if isinstance(res, dict) else "") or str(res)

    # 3) summary 저장(기존 로직 유지)
    manager.summarize_and_save(episode_no, full_text)

    # 4) state 구성
    world_state = _load_world_state()
    history_state = _load_json(manager.history_file, default={})
    story_state = {"world": world_state, "history": history_state}

    # 5) character config
    character_config = _load_character_config()

    # 6) facts 추출 + raw_text 주입(핵심)
    episode_facts = manager.extract_facts(episode_no, full_text, story_state)
    if isinstance(episode_facts, dict):
        episode_facts["raw_text"] = full_text
    else:
        episode_facts = {"raw_text": full_text}

    # 7) consistency
    issues = check_consistency(
        episode_facts=episode_facts,
        character_config=character_config,
        plot_config={},
        story_state=story_state,
    )

    # 8) finalize(report)
    report = finalize_episode(episode_no, episode_facts, issues)

    return {
        "episode_no": episode_no,
        "full_text_len": len(full_text or ""),
        "edits": report.get("edits", []),
    }

import json
import os
from typing import Any, Dict


def _read_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state(episode_no: int) -> Dict[str, Any]:
    """
    ✅ FastAPI에서 안전하게 호출하는 load_state
    - LLM/외부 패키지 import 안 함
    - plot.json / story_history.json 기반으로 "이전 화까지" 상태만 반환
    """
    if not isinstance(episode_no, int) or episode_no < 1:
        raise ValueError("episode_no는 1 이상의 정수여야 합니다.")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    plot_path = os.path.join(base_dir, "../../../data/plot.json")
    history_path = os.path.join(base_dir, "story_history.json")

    plot = _read_json(plot_path, default={})
    history = _read_json(history_path, default={})

    last_episode = max(0, episode_no - 1)

    prev_summary = ""
    if str(last_episode) in history and isinstance(history[str(last_episode)], dict):
        prev_summary = str(history[str(last_episode)].get("summary", ""))

    characters = plot.get("characters", [])
    world_view = plot.get("world_view", {})
    main_conflict = plot.get("main_conflict", "")

    if not isinstance(characters, list):
        characters = []
    if not isinstance(world_view, dict):
        world_view = {}

    return {
        "last_episode": last_episode,
        "prev_summary": prev_summary,
        "global_settings": {
            "characters": characters,
            "world_view": world_view,
            "main_conflict": main_conflict,
        },
    }

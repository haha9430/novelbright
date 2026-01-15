import json
import os
from typing import Any, Dict, List


def _read_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _as_list_str(x: Any) -> List[str]:
    if isinstance(x, list):
        out: List[str] = []
        for it in x:
            s = str(it).strip()
            if s:
                out.append(s)
        return out
    if isinstance(x, str) and x.strip():
        return [x.strip()]
    return []


def _as_str(x: Any) -> str:
    if isinstance(x, str):
        return x
    if x is None:
        return ""
    return str(x)


def load_state(episode_no: int) -> Dict[str, Any]:
    """
    FastAPI에서 호출하는 상태 로더

    ✔ plot.json 최신 구조(summary/genre)만 사용
    ✔ important_parts 제거
    """
    if not isinstance(episode_no, int) or episode_no < 1:
        raise ValueError("episode_no는 1 이상의 정수여야 합니다.")

    pvc_dir = "/app/app/data"

    if os.path.exists(pvc_dir):
        plot_path = os.path.join(pvc_dir, "plot.json")
        history_path = os.path.join(pvc_dir, "story_history.json")
    else:
        # 로컬 환경용 하위 호환성 유지
        base_dir = os.path.dirname(os.path.abspath(__file__))
        plot_path = os.path.join(base_dir, "../../../data/plot.json")
        history_path = os.path.join(base_dir, "story_history.json")

    plot = _read_json(plot_path, default={})
    history = _read_json(history_path, default={})

    if not isinstance(plot, dict):
        plot = {}
    if not isinstance(history, dict):
        history = {}

    last_episode = max(0, episode_no - 1)

    prev_summary = ""
    if str(last_episode) in history and isinstance(history[str(last_episode)], dict):
        prev_summary = _as_str(history[str(last_episode)].get("summary", ""))

    # ======================================================
    # ✅ 최신 plot.json 구조
    # ======================================================
    summary_list = _as_list_str(plot.get("summary", []))
    genre_list = _as_list_str(plot.get("genre", []))

    # ======================================================
    # ✅ 기존 프론트 구조로 매핑
    # ======================================================
    world_view = {
        "summary": "\n".join(summary_list),
    }

    main_conflict = summary_list[0] if summary_list else ""

    characters = plot.get("characters", [])
    if not isinstance(characters, list):
        characters = []

    return {
        "last_episode": last_episode,
        "prev_summary": prev_summary,
        "global_settings": {
            "characters": characters,
            "world_view": world_view,
            "main_conflict": main_conflict,
            "genre": genre_list,
        },
    }

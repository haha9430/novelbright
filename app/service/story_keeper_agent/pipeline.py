from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import ValidationError

from app.service.story_keeper_agent.ingest_episode import ingest_episode, IngestEpisodeRequest
from app.service.story_keeper_agent.ingest_episode.chunking import split_into_chunks
from app.service.story_keeper_agent.load_state.extracter import PlotManager
from app.service.story_keeper_agent.rules.check_consistency import check_consistency
from app.service.story_keeper_agent.finalize_episode import finalize_episode


def _project_root() -> Path:
    # app/service/story_keeper_agent/pipeline.py -> 프로젝트 루트
    return Path(__file__).resolve().parents[3]


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_world_state(root: Path) -> Dict[str, Any]:
    path = root / "app" / "data" / "plot.json"
    data = _load_json(path, default={})
    return data if isinstance(data, dict) else {}


def _load_character_config(root: Path) -> Dict[str, Any]:
    path = root / "app" / "data" / "characters.json"
    data = _load_json(path, default={})
    return data if isinstance(data, dict) else {"characters": []}


def _normalize_severity(s: Optional[str]) -> str:
    ss = (s or "medium").strip().lower()
    if ss not in ("low", "medium", "high"):
        ss = "medium"
    return ss


def run_pipeline(episode_no: int, raw_text: str, severity: Optional[str] = None) -> Dict[str, Any]:
    """
    ✅ UI severity를 '임계치(threshold)'로 반영하도록 수정
    """
    root = _project_root()

    try:
        env_path = root / ".env"
        if env_path.exists():
            load_dotenv(str(env_path))
    except Exception:
        pass

    sev = _normalize_severity(severity)

    print(f"\n🚀 [PIPELINE] episode={episode_no}, severity_threshold={sev}")

    if not isinstance(raw_text, str) or not raw_text.strip():
        return {"episode_no": int(episode_no), "full_text_len": 0, "edits": []}

    manager = PlotManager()

    # 1) Chunking
    try:
        chunks = split_into_chunks(raw_text, max_len=2500, min_len=1500)
    except Exception as e:
        print(f"❌ chunking error: {e}")
        return {"episode_no": int(episode_no), "full_text_len": 0, "edits": []}

    # 2) Ingest
    full_text = ""
    try:
        try:
            req = IngestEpisodeRequest(episode_no=int(episode_no), chunks=chunks)
        except ValidationError:
            req = IngestEpisodeRequest(episode_no=int(episode_no), text_chunks=chunks)

        res = ingest_episode(req=req) if "req" in ingest_episode.__code__.co_varnames else ingest_episode(req)
        full_text = getattr(res, "full_text", None) or (res.get("full_text") if isinstance(res, dict) else "") or ""
    except Exception:
        print("❌ ingest error")
        traceback.print_exc()
        return {"episode_no": int(episode_no), "full_text_len": 0, "edits": []}

    if not full_text.strip():
        return {"episode_no": int(episode_no), "full_text_len": 0, "edits": []}

    # 3) Summary 저장 (실패해도 계속)
    try:
        _ = manager.summarize_and_save(int(episode_no), full_text)
    except Exception as e:
        print(f"⚠️ summarize/save failed (continue): {e}")

    # 4) Load state
    try:
        world_state = _load_world_state(root)
        history_state = _load_json(manager.history_file, default={})
        story_state = {"world": world_state, "history": history_state}
    except Exception as e:
        print(f"❌ state load error: {e}")
        return {"episode_no": int(episode_no), "full_text_len": len(full_text), "edits": []}

    # 5) Consistency check  ✅ severity_threshold 전달
    issues = []
    episode_facts = {}
    try:
        character_config = _load_character_config(root)

        episode_facts = manager.extract_facts(int(episode_no), full_text, story_state)
        if isinstance(episode_facts, dict):
            episode_facts["raw_text"] = full_text
        else:
            episode_facts = {"raw_text": full_text}

        issues = check_consistency(
            episode_facts=episode_facts,
            character_config=character_config,
            plot_config=world_state,
            story_state=story_state,
            severity_threshold=sev,
        )
    except Exception:
        print("❌ consistency check error")
        traceback.print_exc()
        issues = []

    # 6) Finalize
    try:
        report = finalize_episode(int(episode_no), episode_facts, issues)
        return {
            "episode_no": int(episode_no),
            "full_text_len": len(full_text),
            "edits": report.get("edits", []) if isinstance(report, dict) else [],
        }
    except Exception as e:
        print(f"❌ finalize error: {e}")
        return {"episode_no": int(episode_no), "full_text_len": len(full_text), "edits": []}

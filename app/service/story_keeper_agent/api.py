import sys
import os
import json
import inspect

sys.path.insert(0, os.getcwd())

from fastapi import APIRouter, HTTPException, Body, Form, Query
from pydantic import ValidationError

from app.service.story_keeper_agent.ingest_episode import (
    ingest_episode,
    IngestEpisodeRequest,
)
from app.service.story_keeper_agent.ingest_episode.chunking import split_into_chunks
from app.service.story_keeper_agent.load_state.extracter import PlotManager

# ✅ 최종 결과(필터 포함)용
from app.service.story_keeper_agent.rules.check_consistency import check_consistency
from app.service.story_keeper_agent.finalize_episode import issues_to_edits

# ✅ 룰별 raw 디버깅용(직접 호출)
from app.service.story_keeper_agent.rules.world_rules import check_world_consistency
from app.service.story_keeper_agent.rules.character_rules import check_character_consistency
from app.service.story_keeper_agent.rules.plot_rules import check_plot_consistency

from app.service.characters import upsert_character

router = APIRouter(prefix="/story", tags=["story-keeper"])
manager = PlotManager()


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
    here = os.getcwd()
    path = os.path.join(here, "app", "data", "plot.json")
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
    here = os.getcwd()
    path = os.path.join(
        here,
        "app",
        "service",
        "story_keeper_agent",
        "load_state",
        "story_history.json",
    )
    return _safe_read_json(path)


def _load_character_config() -> dict:
    here = os.getcwd()
    path = os.path.join(here, "app", "data", "characters.json")
    if not os.path.exists(path):
        return {"characters": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"characters": []}

    # dict(name->obj) / list 둘 다 대응
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
    try:
        sig = inspect.signature(upsert_character)
        params = sig.parameters

        text_keys = [
            "text",
            "content",
            "profile",
            "description",
            "setting",
            "settings",
            "raw",
            "data",
            "prompt",
            "value",
            "info",
            "bio",
        ]

        kwargs = {}
        if "name" in params:
            kwargs["name"] = name

        chosen_text_key = None
        for k in text_keys:
            if k in params:
                chosen_text_key = k
                break

        if chosen_text_key:
            kwargs[chosen_text_key] = text
            if "name" in params:
                return upsert_character(**kwargs)
            return upsert_character(name, **{chosen_text_key: text})

        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return upsert_character(name=name, text=text)

        return upsert_character(name, text)

    except TypeError:
        return upsert_character(name, text)
    except Exception:
        raise


# =========================
# 1) World/Plot Setting
# =========================
@router.post(
    "/world_setting",
    summary="World/Plot Setting",
    description="설정 입력 -> plot.json 갱신(PlotManager 내부 저장)",
)
def world_setting(text: str = Body(..., media_type="text/plain")):
    return manager.update_global_settings(text)


# =========================
# 2) Character Setting
# =========================
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


# =========================
# 3) Manuscript Feedback
# =========================
@router.post(
    "/manuscript_feedback",
    summary="Manuscript Feedback",
    description="원고 업로드 -> plot.json/characters.json/story_history.json과 비교 피드백",
)
def manuscript_feedback(
    episode_no: int,
    text: str = Body(..., media_type="text/plain"),
    debug_raw: bool = Query(False, description="룰별 raw 이슈를 debug에 포함할지"),
):
    try:
        full_text_str = text or ""
        if not full_text_str.strip():
            raise ValueError("원고가 비어있습니다.")

        # ✅ plot.json 로드 (세계관 포함)
        plot_config = _load_plot_config()
        world = _extract_world_from_plot(plot_config)

        # ✅ story_history.json 로드
        history = _load_story_history()

        # ✅ characters.json 로드
        character_config = _load_character_config()

        story_state = {"world": world, "history": history}

        # 청크 split + ingest
        chunks = split_into_chunks(full_text_str)
        ingest_episode(req=IngestEpisodeRequest(episode_no=episode_no, text_chunks=chunks))

        # extract_facts + raw_text 삽입
        episode_facts = manager.extract_facts(episode_no, full_text_str, story_state)
        if isinstance(episode_facts, dict):
            episode_facts["raw_text"] = full_text_str
        else:
            episode_facts = {"raw_text": full_text_str}

        # =========================
        # ✅ 1) 룰별 raw 실행 (원인 파악용)
        # =========================
        raw_world = check_world_consistency(episode_facts, plot_config)
        raw_char = check_character_consistency(episode_facts, character_config, story_state)
        raw_plot = check_plot_consistency(episode_facts, plot_config, story_state)

        # =========================
        # ✅ 2) 최종 필터(check_consistency) 실행
        # =========================
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

        issues_count = len(issues) if isinstance(issues, list) else 0
        edits_count = len(edits) if isinstance(edits, list) else 0

        debug_block = {
            "issues_count": issues_count,
            "edits_count": edits_count,
            "full_text_len": len(full_text_str),
            "plot_loaded": bool(plot_config),
            "world_loaded": bool(world),
            "history_loaded": bool(history),
            "character_count": len(character_config.get("characters", [])) if isinstance(character_config, dict) else 0,

            # ✅ 여기부터가 핵심: "룰이 실제로 뭘 뽑았는지" 바로 보임
            "raw_counts": {
                "world": len(raw_world) if isinstance(raw_world, list) else -1,
                "character": len(raw_char) if isinstance(raw_char, list) else -1,
                "plot": len(raw_plot) if isinstance(raw_plot, list) else -1,
            },
            "raw_fail_flags": {
                # 룰 함수가 실패하면 title에 '검사 실패'가 들어가게 해둔 전제(없으면 False)
                "world_failed": any(getattr(x, "title", "").endswith("실패") for x in raw_world) if isinstance(raw_world, list) else True,
                "character_failed": any(getattr(x, "title", "").endswith("실패") for x in raw_char) if isinstance(raw_char, list) else True,
                "plot_failed": any(getattr(x, "title", "").endswith("실패") for x in raw_plot) if isinstance(raw_plot, list) else True,
            },
        }

        if debug_raw:
            # 너무 길어질 수 있으니, 최대 5개씩만 샘플로
            debug_block["raw_samples"] = {
                "world": [x.to_dict() for x in raw_world[:5]] if isinstance(raw_world, list) else [],
                "character": [x.to_dict() for x in raw_char[:5]] if isinstance(raw_char, list) else [],
                "plot": [x.to_dict() for x in raw_plot[:5]] if isinstance(raw_plot, list) else [],
            }

        return {
            "episode_no": episode_no,
            "issues": issues,
            "edits": edits,
            "debug": debug_block,
        }

    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

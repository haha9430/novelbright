import sys
import os
import json
import inspect

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
    """
    upsert_character() 시그니처가 프로젝트마다 달라서
    여기서 자동으로 맞춰서 호출한다.
    """
    try:
        sig = inspect.signature(upsert_character)
        params = sig.parameters

        # 키워드 인자 후보들 (프로젝트마다 이름 달라서 대비)
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

        # name 키가 따로 있으면 맞춰줌 (대부분 name이라서 기본은 name)
        if "name" in params:
            kwargs["name"] = name
        else:
            # name이 없으면 1번째 positional로 밀어넣는 쪽으로 간다
            pass

        # text 계열 파라미터 찾기
        chosen_text_key = None
        for k in text_keys:
            if k in params:
                chosen_text_key = k
                break

        if chosen_text_key:
            kwargs[chosen_text_key] = text
            # name 키워드가 없을 때는 positional+keyword 섞이면 위험하니 안전하게 처리
            if "name" in params:
                return upsert_character(**kwargs)
            else:
                return upsert_character(name, **{chosen_text_key: text})

        # **kwargs 받는 함수면 그냥 text로 넣어보기
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return upsert_character(name=name, text=text)

        # 마지막 수단: (name, text) positional로 호출
        return upsert_character(name, text)

    except TypeError:
        # 혹시 위에서 또 안 맞으면 최종 fallback
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

        # 기존 PlotManager/기존 코드 호환용 (world/history 둘 다)
        story_state = {"world": world, "history": history}

        # 청크 split
        chunks = split_into_chunks(full_text_str)

        # ingest
        ingest_episode(req=IngestEpisodeRequest(episode_no=episode_no, text_chunks=chunks))

        # extract_facts (원고 원문도 함께 전달)
        episode_facts = manager.extract_facts(episode_no, full_text_str, story_state)

        if isinstance(episode_facts, dict):
            episode_facts["raw_text"] = full_text_str
        else:
            episode_facts = {"raw_text": full_text_str}

        # ✅ JSON 비교 기반 룰만
        issues = check_consistency(
            episode_facts=episode_facts,
            character_config=character_config,
            plot_config=plot_config,
            story_state=story_state,
        )

        # issues -> edits 변환
        edits = issues_to_edits(
            issues,
            episode_no=episode_no,
            raw_text=full_text_str,
        )

        issues_count = len(issues) if isinstance(issues, list) else 0
        edits_count = len(edits) if isinstance(edits, list) else 0

        return {
            "episode_no": episode_no,
            "issues": issues,
            "edits": edits,
            "debug": {
                "issues_count": issues_count,
                "edits_count": edits_count,
                "full_text_len": len(full_text_str or ""),
                "plot_loaded": bool(plot_config),
                "world_loaded": bool(world),
                "history_loaded": bool(history),
                "character_count": len(character_config.get("characters", []))
                if isinstance(character_config, dict)
                else 0,
            },
        }

    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

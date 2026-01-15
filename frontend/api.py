# frontend/api.py
import requests
import streamlit as st
import io
import json
import re
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def _project_root() -> Path:
    # frontend/api.py -> 프로젝트 루트
    return Path(__file__).resolve().parents[1]


def _data_path(filename: str) -> Path:
    return _project_root() / "app" / "data" / filename


def _safe_read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def _strip_html_to_text(html: str) -> str:
    if not isinstance(html, str):
        return ""
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _pick_first_str(d: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _normalize_storykeeper_items(raw: Any) -> List[Dict[str, Any]]:
    """
    run_pipeline 결과에서 edits를 표준 포맷으로 정리해서 UI에 넘김
    """
    if isinstance(raw, dict):
        if isinstance(raw.get("edits"), list):
            items = raw["edits"]
        elif isinstance(raw.get("issues"), list):
            items = raw["issues"]
        else:
            items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    out: List[Dict[str, Any]] = []

    for it in items:
        if not isinstance(it, dict):
            continue

        sev = str(it.get("severity", "medium")).strip().lower()
        if sev not in ("low", "medium", "high"):
            sev = "medium"

        out.append(
            {
                "severity": sev,
                "type_label": _pick_first_str(it, ["type_label", "type"]) or "분석 결과",
                "title": _pick_first_str(it, ["title"]) or "설정 충돌",
                "location": _pick_first_str(it, ["location"]) or "",
                "sentence": _pick_first_str(it, ["sentence"]) or "",
                "reason": _pick_first_str(it, ["reason"]) or "",
                "rewrite": _pick_first_str(it, ["rewrite"]) or "",
            }
        )

    return out


# =========================
# 1) 스토리키퍼 분석
# =========================
def analyze_text_api(doc_id: str, content: str, episode_no: int = 1, severity: str = "medium") -> List[Dict[str, Any]]:
    """
    ✅ 여기서 severity는 UI 필터용
    ✅ 분석 자체는 항상 전체(low threshold) 생성으로 돌려서,
       '확실한 충돌인데 0건' 같은 상황을 줄임
    """
    plain = _strip_html_to_text(content)

    try:
        from app.service.story_keeper_agent.pipeline import run_pipeline
    except Exception as e:
        st.error(f"파이프라인 import 실패: {e}")
        return []

    try:
        # ✅ 핵심: 항상 low로 돌려서 전부 받기
        raw = run_pipeline(episode_no=int(episode_no), raw_text=plain, severity="low")
    except Exception as e:
        st.error(f"파이프라인 실행 실패: {e}")
        return []

    return _normalize_storykeeper_items(raw)


# =========================
# 2) 요약 저장(히스토리)
# =========================
def save_story_history_api(episode_no: int, full_text: str) -> Tuple[bool, Dict[str, Any]]:
    try:
        from app.service.story_keeper_agent.load_state.extracter import StoryHistoryManager
    except Exception as e:
        return False, {"status": "error", "message": f"StoryHistoryManager import 실패: {e}"}

    try:
        manager = StoryHistoryManager()
        plain = _strip_html_to_text(full_text)
        res = manager.summarize_and_save_episode(episode_no=int(episode_no), full_text=plain)
        ok = isinstance(res, dict) and res.get("status") == "success"
        return ok, res if isinstance(res, dict) else {"status": "error", "message": "unknown"}
    except Exception as e:
        return False, {"status": "error", "message": str(e)}


# =========================
# 3) 문서 저장 (지금은 UI 유지용)
# =========================
def save_document_api(doc_id: str, title: str, content: str) -> bool:
    return True


# =========================
# 4) 캐릭터 저장 (ImportError 해결 포인트)
# =========================
def save_character_api(name: str, description: str) -> bool:
    """
    components/common.py에서 import하는 함수
    """
    if not name or not description:
        return False

    try:
        from app.service.characters import upsert_character
    except Exception as e:
        st.error(f"characters 모듈 import 실패: {e}")
        return False

    try:
        db_path = str(_data_path("characters.json"))
        res = upsert_character(name=name, features=description, db_path=db_path)
        return isinstance(res, dict) and res.get("status") == "success"
    except Exception as e:
        st.error(f"캐릭터 저장 오류: {e}")
        return False


# =========================
# 5) 세계관 저장 (plot.json)
# =========================
def save_world_setting_api(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False

    # 기존 포맷 유지: summary/genre/important_parts
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    summary = lines[:5] if lines else [text[:180]]

    data = {
        "summary": summary,
        "genre": [],  # 장르는 '명시된 것만' 원칙이면 여기서 자동추론 금지
        "important_parts": summary[:12],
    }

    try:
        _safe_write_json(_data_path("plot.json"), data)
        return True
    except Exception as e:
        st.error(f"세계관 저장 실패: {e}")
        return False


# =========================
# 6) 자료(materials)
# =========================
def save_material_api(material_data: Dict[str, Any]) -> bool:
    try:
        path = _data_path("materials.json")
        db = _safe_read_json(path, default={"materials": []})
        if not isinstance(db, dict):
            db = {"materials": []}
        if "materials" not in db or not isinstance(db["materials"], list):
            db["materials"] = []

        db["materials"].append(material_data)
        _safe_write_json(path, db)
        return True
    except Exception as e:
        st.error(f"자료 저장 실패: {e}")
        return False


def delete_material_api(material_id: str) -> bool:
    try:
        path = _data_path("materials.json")
        db = _safe_read_json(path, default={"materials": []})
        if not isinstance(db, dict) or "materials" not in db or not isinstance(db["materials"], list):
            return True

        db["materials"] = [m for m in db["materials"] if str(m.get("id")) != str(material_id)]
        _safe_write_json(path, db)
        return True
    except Exception as e:
        st.error(f"자료 삭제 실패: {e}")
        return False

def analyze_clio_api(current_doc, content_source):
    try:
        content_source_txt = io.BytesIO(content_source.encode("utf-8"))
        content_source_txt.name = f"{current_doc['title']}.txt"
        form_data_analyzer = {"file": (content_source_txt.name, content_source_txt, "text/plain")}

        # [변경됨] 하드코딩 URL 제거 -> BASE_URL 변수 사용
        api_url = f"{BASE_URL}/manuscript/analyze"

        # 디버깅용 로그 (Streamlit 화면에는 안 보이고 컨테이너 로그에 찍힘)
        print(f"📡 API 호출 시도: {api_url}")

        res = requests.post(
            api_url,
            files=form_data_analyzer,
            data={"title": current_doc['title']}
        )

        print(f"✅ 응답 코드: {res.status_code}")

        if res.status_code == 200:
            return res.json()
        else:
            st.error(f"오류: {res.text}")
    except Exception as e:
        st.error(f"연결 실패: {e}")
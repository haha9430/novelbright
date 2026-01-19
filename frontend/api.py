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
# 1) 스토리키퍼 분석 (API 호출)
# =========================
def analyze_text_api(doc_id: str, content: str, episode_no: int = 1, severity: str = "medium") -> List[Dict[str, Any]]:
    """
    POST /manuscript_feedback 호출
    """
    plain = _strip_html_to_text(content)
    url = f"{BASE_URL}/story/manuscript_feedback"

    # 쿼리 파라미터
    params = {
        "episode_no": episode_no,
        "debug_raw": False
    }

    # Body (text/plain)
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    try:
        response = requests.post(
            url,
            params=params,
            data=plain.encode('utf-8'),
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            # UI 필터링을 위한 정규화 (severity 필터는 UI에서 처리한다고 했으므로 여기선 raw 데이터 반환)
            return _normalize_storykeeper_items(result)
        else:
            st.error(f"분석 요청 실패: {response.status_code} - {response.text}")
            return []

    except Exception as e:
        st.error(f"API 통신 오류: {e}")
        return []


# =========================
# 2) 요약 저장(히스토리) (API 호출)
# =========================
def save_story_history_api(episode_no: int, full_text: str) -> Tuple[bool, Dict[str, Any]]:
    """
    백엔드의 /manuscript_feedback API가 내부적으로
    ingest_episode(히스토리 저장)를 수행하므로 동일한 API를 호출합니다.
    """
    plain = _strip_html_to_text(full_text)
    url = f"{BASE_URL}/story/manuscript_feedback"

    params = {"episode_no": episode_no, "debug_raw": False}
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    try:
        # 단순히 저장/학습이 목적이므로 결과값(issues)은 크게 중요하지 않음
        response = requests.post(
            url,
            params=params,
            data=plain.encode('utf-8'),
            headers=headers
        )

        if response.status_code == 200:
            return True, {"status": "success", "message": "History updated via API"}
        else:
            return False, {"status": "error", "message": response.text}

    except Exception as e:
        return False, {"status": "error", "message": str(e)}


# =========================
# 3) 문서 저장 (UI 유지용)
# =========================
def save_document_api(doc_id: str, title: str, content: str) -> bool:
    """
    백엔드에 '문서 자체'를 저장하는 API는 없으므로
    (에이전트 분석용 API만 존재),
    프론트엔드 단독 기능(DB/파일저장)으로 유지하거나
    추후 별도 CMS API가 필요합니다.
    """
    return True


# =========================
# 4) 캐릭터 저장 (API 호출)
# =========================
def save_character_api(name: str, description: str) -> bool:
    """
    POST /character_setting 호출
    (Form Data 전송)
    """
    if not name or not description:
        return False

    url = f"{BASE_URL}/story/character_setting"

    # Form Data 형식
    form_data = {
        "name": name,
        "text": description
    }

    try:
        response = requests.post(url, data=form_data)

        if response.status_code == 200:
            return True
        else:
            st.error(f"캐릭터 저장 실패: {response.text}")
            return False
    except Exception as e:
        st.error(f"API 통신 오류: {e}")
        return False


# =========================
# 5) 세계관 저장 (API 호출)
# =========================
def save_world_setting_api(content: str) -> bool:
    """
    POST /world_setting 호출
    (Body: text/plain)
    """
    text = (content or "").strip()
    if not text:
        return False

    url = f"{BASE_URL}/story/world_setting"
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    try:
        response = requests.post(
            url,
            data=text.encode('utf-8'),
            headers=headers
        )

        if response.status_code == 200:
            return True
        else:
            st.error(f"세계관 저장 실패: {response.text}")
            return False

    except Exception as e:
        st.error(f"API 통신 오류: {e}")
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
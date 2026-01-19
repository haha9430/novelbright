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


def get_story_history_api(timeout: int = 8) -> Tuple[Dict[str, Any], str]:
    url = f"{BASE_URL}/story/history"
    try:
        res = requests.get(url, timeout=timeout)
        if res.status_code != 200:
            return {}, f"히스토리 요청 실패: {res.status_code} - {res.text}"

        data = res.json()

        if isinstance(data, dict) and isinstance(data.get("history"), dict):
            return data["history"], ""

        if isinstance(data, dict):
            return data, ""

        return {}, "히스토리 응답 형식이 올바르지 않습니다."
    except Exception as e:
        return {}, f"히스토리 API 통신 오류: {e}"


def get_world_setting_api(timeout: int = 8) -> Tuple[Dict[str, Any], str]:
    url = f"{BASE_URL}/story/world_setting"
    try:
        res = requests.get(url, timeout=timeout)
        if res.status_code != 200:
            return {}, f"세계관 요청 실패: {res.status_code} - {res.text}"

        data = res.json()
        if isinstance(data, dict) and isinstance(data.get("plot"), dict):
            return data["plot"], ""
        if isinstance(data, dict):
            return data, ""
        return {}, "세계관 응답 형식이 올바르지 않습니다."
    except Exception as e:
        return {}, f"세계관 API 통신 오류: {e}"


def analyze_text_api(doc_id: str, content: str, episode_no: int = 1, severity: str = "medium") -> List[Dict[str, Any]]:
    forwarding = _strip_html_to_text(content)
    url = f"{BASE_URL}/story/manuscript_feedback"

    params = {"episode_no": episode_no, "debug_raw": False}
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    try:
        response = requests.post(url, params=params, data=forwarding.encode("utf-8"), headers=headers)
        if response.status_code == 200:
            return _normalize_storykeeper_items(response.json())
        st.error(f"분석 요청 실패: {response.status_code} - {response.text}")
        return []
    except Exception as e:
        st.error(f"API 통신 오류: {e}")
        return []


def save_story_history_api(episode_no: int, full_text: str) -> Tuple[bool, Dict[str, Any]]:
    plain = _strip_html_to_text(full_text)
    url = f"{BASE_URL}/story/manuscript_feedback"

    params = {"episode_no": episode_no, "debug_raw": False}
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    try:
        response = requests.post(url, params=params, data=plain.encode("utf-8"), headers=headers)
        if response.status_code == 200:
            return True, {"status": "success", "message": "History updated via API"}
        return False, {"status": "error", "message": response.text}
    except Exception as e:
        return False, {"status": "error", "message": str(e)}


def save_document_api(doc_id: str, title: str, content: str) -> bool:
    return True


def save_character_api(name: str, description: str) -> bool:
    if not name or not description:
        return False

    url = f"{BASE_URL}/story/character_setting"
    form_data = {"name": name, "text": description}

    try:
        response = requests.post(url, data=form_data)
        if response.status_code == 200:
            return True
        st.error(f"캐릭터 저장 실패: {response.text}")
        return False
    except Exception as e:
        st.error(f"API 통신 오류: {e}")
        return False


def save_world_setting_api(content: str) -> bool:
    # ✅ 빈 값도 허용 (삭제용)
    text = (content or "")

    url = f"{BASE_URL}/story/world_setting"
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    try:
        response = requests.post(url, data=text.encode("utf-8"), headers=headers)
        if response.status_code == 200:
            return True
        st.error(f"세계관 저장 실패: {response.text}")
        return False
    except Exception as e:
        st.error(f"API 통신 오류: {e}")
        return False


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

        api_url = f"{BASE_URL}/manuscript/analyze"
        print(f"📡 API 호출 시도: {api_url}")

        res = requests.post(api_url, files=form_data_analyzer, data={"title": current_doc["title"]})
        print(f"✅ 응답 코드: {res.status_code}")

        if res.status_code == 200:
            return res.json()
        st.error(f"오류: {res.text}")
    except Exception as e:
        st.error(f"연결 실패: {e}")


def ingest_file_to_backend(text: str, upload_type: str) -> Tuple[bool, str]:
    if not text.strip():
        return False, "추출된 텍스트가 없습니다."

    url = f"{BASE_URL}/story/ingest"
    payload = {"text": text, "type": upload_type}

    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                return True, result.get("message", "성공적으로 처리되었습니다.")
            return False, result.get("message", "백엔드 분석 실패")
        return False, f"서버 응답 오류 ({response.status_code}): {response.text}"
    except Exception as e:
        return False, f"연결 오류 발생: {str(e)}"

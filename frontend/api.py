# frontend/api.py
import requests
import streamlit as st
import io
import json
import re
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

BASE_URL = BASE_URL = os.getenv("BACKEND_URL", "/api")
# /api/story/history 로 호출



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
    # 간단 제거
    text = re.sub(r"<[^>]+>", "", html)
    return text


# -----------------------------
# ✅ 추가: story_history 불러오기
# -----------------------------
def get_story_history_api(timeout: int = 8) -> Tuple[Dict[str, Any], str]:
    """
    백엔드 /story/history 호출해서 히스토리(dict)를 가져온다.
    return: (history_dict, error_message)
      - 성공: (history, "")
      - 실패: ({}, "에러")
    """
    try:
        url = f"{BASE_URL}/story/history"
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return {}, f"백엔드 응답 오류: {r.status_code}"

        data = r.json()
        # 백엔드가 {"history": {...}}로 주는 형태
        if isinstance(data, dict) and isinstance(data.get("history"), dict):
            return data["history"], ""
        # 혹시 그냥 dict를 바로 주는 경우도 대응
        if isinstance(data, dict):
            return data, ""

        return {}, "history 형식이 dict가 아님"
    except Exception as e:
        return {}, f"백엔드 연결 실패: {e}"



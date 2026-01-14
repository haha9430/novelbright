from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage


def _project_root() -> Path:
    # app/service/story_keeper_agent/load_state/extracter.py -> 프로젝트 루트
    return Path(__file__).resolve().parents[4]


def _read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        # 여기서 예외를 다시 올리면 파이프라인이 터지니까, 호출부에서 잡게끔 raise 유지
        raise e


def _extract_explicit_genre(text: str) -> List[str]:
    """
    장르 자동추론 X
    '장르:' / 'genre:' 처럼 사용자가 명시한 것만 추출
    """
    if not isinstance(text, str):
        return []
    m = re.search(r"(장르|genre)\s*[:：]\s*(.+)", text, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(2).strip()
    parts = re.split(r"[,/|·\s]+", raw)
    out: List[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out[:10]


class PlotManager:
    """
    (친구 코드 기반) plot.json / story_history.json 관리 + LLM 요약/팩트추출
    - 절대경로 제거: 프로젝트 루트 기준으로 경로 자동 설정
    """

    def __init__(self):
        self._fix_ssl_cert_env()

        # .env는 루트에 있으면 로드 (없어도 에러 X)
        try:
            env_path = _project_root() / ".env"
            if env_path.exists():
                load_dotenv(str(env_path))
        except Exception:
            pass

        try:
            self.llm = ChatUpstage(model="solar-pro")
        except Exception:
            self.llm = None

        root = _project_root()
        self.global_setting_file = root / "app" / "data" / "plot.json"
        self.characters_file = root / "app" / "data" / "characters.json"
        self.history_file = root / "app" / "service" / "story_keeper_agent" / "load_state" / "story_history.json"

        print(f"📂 plot.json: {self.global_setting_file}")
        print(f"📂 story_history.json: {self.history_file}")

    def _fix_ssl_cert_env(self) -> None:
        try:
            import certifi

            cafile = certifi.where()
            os.environ["SSL_CERT_FILE"] = cafile
            os.environ["REQUESTS_CA_BUNDLE"] = cafile
            os.environ["CURL_CA_BUNDLE"] = cafile
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # 강력 JSON 파싱
    # --------------------------------------------------------------------------
    def _safe_json(self, raw: str) -> Dict[str, Any]:
        if not raw:
            return {}
        raw = raw.strip()

        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()

        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not m:
            return {}

        try:
            return json.loads(m.group(0))
        except Exception:
            return {}

    # =========================
    # 1) 원고 요약 및 저장 (친구 함수명 유지)
    # =========================
    def summarize_and_save(self, episode_no: int, full_text: str) -> Dict[str, Any]:
        if not isinstance(full_text, str) or not full_text.strip():
            return {"status": "error", "message": "empty text"}

        history_data = _read_json(self.history_file, default={})
        prev_flow = history_data.get(str(int(episode_no) - 1), {}).get("story_flow", "")

        # LLM 없으면 fallback
        if self.llm is None:
            result = {
                "title": f"{episode_no}화",
                "summary": (full_text.strip()[:300] + "...") if len(full_text.strip()) > 300 else full_text.strip(),
                "story_flow": prev_flow,
            }
        else:
            prompt = f"""
너는 웹소설 편집자다.
아래 원고를 요약하여 JSON으로 반환하라.

[규칙]
1) 출력은 오직 JSON만
2) 키는 "title", "summary", "story_flow" (3개 고정)
3) 언어: 한국어
4) story_flow는 "이전 흐름"을 참고하되, 현재 화 내용 기준으로 자연스럽게 갱신

[입력]
이전 흐름: {prev_flow}

원고:
{full_text[:3500]}
"""
            try:
                res = self.llm.invoke(prompt)
                raw = getattr(res, "content", str(res))
                result = self._safe_json(raw) or {}
            except Exception:
                result = {}

            if not result:
                result = {
                    "title": f"{episode_no}화 (자동)",
                    "summary": "요약 생성 실패 (원문 확인 필요)",
                    "story_flow": prev_flow or "정보 없음",
                }

        history_data[str(int(episode_no))] = {
            "episode_no": int(episode_no),
            "title": str(result.get("title", "")),
            "summary": str(result.get("summary", "")),
            "story_flow": str(result.get("story_flow", "")),
        }

        try:
            _write_json(self.history_file, history_data)
            return {"status": "success", "data": history_data[str(int(episode_no))]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================
    # 2) 팩트 추출 (extract_facts)
    # =========================
    def extract_facts(self, episode_no: int, full_text: str, story_state: Dict[str, Any]) -> Dict[str, Any]:
        if self.llm is None:
            return {"episode_no": int(episode_no), "events": [], "characters": [], "state_changes": {}}

        prompt = f"""
Extract facts for consistency check.
Return ONLY JSON.
Keys: "events", "characters", "state_changes".

Input:
{full_text[:3500]}
"""
        try:
            res = self.llm.invoke(prompt)
            raw = getattr(res, "content", str(res))
            result = self._safe_json(raw) or {}
            if not result:
                return {"episode_no": int(episode_no), "events": [], "characters": [], "state_changes": {}}
            result["episode_no"] = int(episode_no)
            return result
        except Exception:
            return {"episode_no": int(episode_no), "events": [], "characters": [], "state_changes": {}}

    # =========================
    # 3) 세계관 저장 (update_global_settings)
    # - genre는 "명시된 것만" 원칙 반영
    # =========================
    def update_global_settings(self, text: str) -> Dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            return {"status": "error", "message": "empty text"}

        # LLM 없으면 프론트처럼 간단 저장
        if self.llm is None:
            summary_lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:5]
            data = {
                "summary": summary_lines if summary_lines else [text.strip()[:180]],
                "genre": _extract_explicit_genre(text),
                "important_parts": summary_lines[:12],
            }
            try:
                _write_json(self.global_setting_file, data)
                return {"status": "success", "data": data}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        prompt = f"""
너는 웹소설 편집자다. 아래 세계관 설정을 정리해서 JSON으로 반환하라.

[규칙]
1) 출력은 JSON만
2) 키: "summary", "genre", "important_parts"
3) genre는 "원문에 명시된 것(예: '장르: ...')"만 넣고, 추측/자동추론 금지
4) summary/important_parts는 원문에서 근거가 드러나게 간단히 정리

[입력]
{text[:6000]}
"""
        try:
            res = self.llm.invoke(prompt)
            raw = getattr(res, "content", str(res))
            data = self._safe_json(raw) or {}

            # genre 강제 보정: LLM이 추론했더라도 명시된 것만 유지
            data["genre"] = _extract_explicit_genre(text)

            if "summary" not in data or not isinstance(data.get("summary"), list):
                # summary가 문자열이면 리스트로
                s = data.get("summary")
                if isinstance(s, str) and s.strip():
                    data["summary"] = [s.strip()]
                else:
                    data["summary"] = []

            if "important_parts" not in data or not isinstance(data.get("important_parts"), list):
                ip = data.get("important_parts")
                if isinstance(ip, str) and ip.strip():
                    data["important_parts"] = [ip.strip()]
                else:
                    data["important_parts"] = []

            _write_json(self.global_setting_file, data)
            return {"status": "success", "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class StoryHistoryManager:
    """
    ✅ 너 프론트(api.py)가 기대하는 인터페이스 제공
    - summarize_and_save_episode(episode_no, full_text)
    """

    def __init__(self):
        self.pm = PlotManager()

    def summarize_and_save_episode(self, *, episode_no: int, full_text: str) -> Dict[str, Any]:
        return self.pm.summarize_and_save(int(episode_no), full_text)

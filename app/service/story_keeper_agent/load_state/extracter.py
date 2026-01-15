from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage


def _project_root() -> Path:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def _split_sentences_ko(text: str) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", t)
    out: List[str] = []
    for p in parts:
        p = p.strip()
        if len(p) < 8:
            continue
        out.append(p)
    return out


def _dedupe_keep_order(items: List[str], *, max_items: int) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        s = (it or "").strip()
        if not s:
            continue
        k = re.sub(r"\s+", " ", s)
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= max_items:
            break
    return out


def _pick_summary(text: str) -> List[str]:
    sents = _split_sentences_ko(text)
    if not sents:
        return []
    summary = _dedupe_keep_order(sents, max_items=8)
    if len(summary) < 4:
        summary = _dedupe_keep_order(sents, max_items=4)
    return summary[:8]


class PlotManager:
    """
    plot.json / story_history.json 관리

    ✅ plot.json 저장 포맷 (딱 2개만)
    {
      "summary": [...],
      "genre": ["..."]   # 최소 1개
    }
    """

    def __init__(self):
        self._fix_ssl_cert_env()

        # .env 로드
        try:
            env_path = _project_root() / ".env"
            if env_path.exists():
                load_dotenv(str(env_path))
        except Exception:
            pass

        self.llm = self._init_llm()

        root = _project_root()
        self.global_setting_file = root / "app" / "data" / "plot.json"
        self.history_file = root / "app" / "data" / "story_history.json"

        print(f"📂 plot.json: {self.global_setting_file}")
        print(f"📂 story_history.json: {self.history_file}")
        print(f"🤖 LLM ready: {self.llm is not None}")

    def _fix_ssl_cert_env(self) -> None:
        try:
            import certifi

            cafile = certifi.where()
            os.environ["SSL_CERT_FILE"] = cafile
            os.environ["REQUESTS_CA_BUNDLE"] = cafile
            os.environ["CURL_CA_BUNDLE"] = cafile
        except Exception:
            pass

    def _init_llm(self) -> Optional[ChatUpstage]:
        key = (os.getenv("UPSTAGE_API_KEY") or "").strip()
        if not key:
            return None

        model = (os.getenv("UPSTAGE_CHAT_MODEL") or "").strip() or "solar-pro"
        try:
            return ChatUpstage(model=model)
        except Exception:
            try:
                return ChatUpstage()
            except Exception:
                return None

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
    # (필수) story_history 저장용
    # =========================
    def summarize_and_save(self, episode_no: int, full_text: str) -> Dict[str, Any]:
        if not isinstance(full_text, str) or not full_text.strip():
            return {"status": "error", "message": "empty text"}

        history_data = _read_json(self.history_file, default={})
        prev_flow = history_data.get(str(int(episode_no) - 1), {}).get("story_flow", "")

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
    # (필수) pipeline이 호출하는 extract_facts
    # - LLM 없어도 파이프라인이 안 죽도록 "빈 구조" 반환
    # =========================
    def extract_facts(self, episode_no: int, full_text: str, story_state: Dict[str, Any]) -> Dict[str, Any]:
        if self.llm is None:
            return {
                "episode_no": int(episode_no),
                "events": [],
                "characters": [],
                "state_changes": {},
            }

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
            data = self._safe_json(raw) or {}
            if not data:
                return {
                    "episode_no": int(episode_no),
                    "events": [],
                    "characters": [],
                    "state_changes": {},
                }
            data["episode_no"] = int(episode_no)

            # 최소 형태 보정
            if "events" not in data or not isinstance(data.get("events"), list):
                data["events"] = []
            if "characters" not in data or not isinstance(data.get("characters"), list):
                data["characters"] = []
            if "state_changes" not in data or not isinstance(data.get("state_changes"), dict):
                data["state_changes"] = {}

            return data
        except Exception:
            return {
                "episode_no": int(episode_no),
                "events": [],
                "characters": [],
                "state_changes": {},
            }

    # =========================
    # 세계관 저장
    # - summary: 원문 문장 기반
    # - genre: AI가 추측해서 최소 1개
    # - important_parts 없음
    # =========================
    def update_global_settings(self, text: str) -> Dict[str, Any]:
        """
        [수정됨] 기존 plot.json 내용을 보존하면서 summary와 genre만 업데이트
        """
        if not isinstance(text, str) or not text.strip():
            return {"status": "error", "message": "empty text"}

        # 1. 요약 및 장르 추출 (기존 로직 유지)
        summary = _pick_summary(text)

        allowed_genres = [
            "로맨스", "로맨스판타지", "현대판타지", "판타지", "무협",
            "헌터/게이트", "회귀", "빙의", "환생", "이세계",
            "대체역사", "역사", "추리/미스터리", "스릴러", "공포",
            "SF", "드라마", "코미디", "액션", "모험", "전쟁",
            "정치", "의학", "성장", "학원", "서바이벌", "디스토피아"
        ]

        genre: List[str] = []

        if self.llm is not None:
            prompt = f"""
너는 웹소설 편집자다. 아래 글을 읽고 장르를 추측해라.
[규칙]
- 출력은 JSON만
- 키는 "genre" 하나만
- genre는 리스트
- 반드시 후보에서만 선택
- 최소 1개, 최대 3개 (절대 비우지 마)
- "기타/일반/모름" 금지

[후보]
{allowed_genres}

[텍스트]
{text[:4500]}
"""
            for _ in range(2):
                try:
                    res = self.llm.invoke(prompt)
                    raw = getattr(res, "content", str(res))
                    data = self._safe_json(raw) or {}
                    g = data.get("genre", [])

                    # (장르 정제 로직 기존 유지)
                    if isinstance(g, str) and g.strip():
                        g_list = [g.strip()]
                    elif isinstance(g, list):
                        g_list = [str(x).strip() for x in g if str(x).strip()]
                    else:
                        g_list = []

                    allowed = set(allowed_genres)
                    banned = {"기타", "일반", "모름", "unknown", "etc"}
                    cleaned: List[str] = []
                    for x in g_list:
                        if x in banned: continue
                        if x not in allowed: continue
                        if x not in cleaned: cleaned.append(x)

                    genre = cleaned[:3]
                    if genre: break
                except Exception:
                    genre = []

        if not genre:
            genre = ["드라마"]

        # =========================================================
        # ✅ [핵심 수정 구간] 기존 데이터 읽기 -> 병합 -> 저장
        # =========================================================

        # 1. 기존 파일이 있으면 읽어옵니다. (없으면 빈 딕셔너리)
        current_data = _read_json(self.global_setting_file, default={})

        # 2. 기존 데이터에 새로운 summary와 genre를 덮어씌웁니다.
        # 이렇게 해야 기존에 있던 'main_characters' 같은 다른 키들이 지워지지 않습니다.
        current_data["summary"] = summary
        current_data["genre"] = genre

        # (선택사항) 분석에 사용된 원본 텍스트도 저장해두면 나중에 유용할 수 있습니다.
        # current_data["last_analysis_text"] = text[:500] + "..."

        try:
            # 3. 병합된 전체 데이터를 저장합니다.
            _write_json(self.global_setting_file, current_data)
            print(f"🌍 [세계관 설정] 업데이트 완료: {self.global_setting_file}")
            return {"status": "success", "data": current_data}
        except Exception as e:
            print(f"🔥 [세계관 설정] 저장 실패: {e}")
            return {"status": "error", "message": str(e)}


class StoryHistoryManager:
    def __init__(self):
        self.pm = PlotManager()

    def summarize_and_save_episode(self, *, episode_no: int, full_text: str) -> Dict[str, Any]:
        return self.pm.summarize_and_save(int(episode_no), full_text)

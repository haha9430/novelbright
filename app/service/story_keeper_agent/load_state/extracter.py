from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# 라이브러리가 없을 경우를 대비한 안전장치
try:
    from dotenv import load_dotenv
    from langchain_upstage import ChatUpstage
except ImportError:
    pass


# =========================================================
# 🛠️ 유틸리티 함수
# =========================================================

def _project_root() -> Path:
    # 현재 파일 위치 기준 프로젝트 루트 찾기 (깊이에 따라 조정 필요)
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


# =========================================================
# 🏛️ PlotManager 클래스
# =========================================================

class PlotManager:
    """
    plot.json / story_history.json 관리 및 세계관 설정 업데이트
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

        # [경로 설정] K8s / Local 하이브리드
        k8s_data_dir = Path("/app/app/data")

        if k8s_data_dir.exists():
            self.data_dir = k8s_data_dir
        else:
            # 로컬 환경용
            self.data_dir = _project_root() / "app" / "data"

        self.global_setting_file = self.data_dir / "plot.json"
        self.history_file = self.data_dir / "story_history.json"

        # 디렉토리 생성 보장
        self.data_dir.mkdir(parents=True, exist_ok=True)
        print(f"📂 Active Data Dir: {self.data_dir}")

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
        # 마크다운 코드 블록 제거
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE | re.MULTILINE).strip()
        raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()

        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not m:
            return {}

        try:
            return json.loads(m.group(0))
        except Exception:
            return {}

    # ---------------------------------------------------------
    # ✅ (핵심 수정) 호환성 유지: episode_no 인자 처리 추가
    # ---------------------------------------------------------
    def update_global_settings(self, text: Union[str, int], episode_no: Optional[Union[int, str]] = 0) -> Dict[
        str, Any]:
        """
        [Ingest용 & Legacy 호환]
        - ingest 호출 시: update_global_settings("텍스트내용") -> episode_no=0
        - 기존 호출 시: update_global_settings(episode_no=1, text="내용") 또는 (1, "내용")
        """

        # 1. 인자 순서/타입 자동 보정 (순서가 바뀌어 들어와도 처리)
        real_text = ""

        # Case A: (text="...", episode_no=...) -> 정상
        if isinstance(text, str):
            real_text = text
        # Case B: (text=1, episode_no="...") -> 순서 바뀜 (episode_no 자리에 텍스트가 들어옴)
        elif isinstance(text, int) and isinstance(episode_no, str):
            real_text = episode_no

        if not real_text or not real_text.strip():
            return {"status": "error", "message": "empty text"}

        # 2. 요약 및 장르 추출
        summary = _pick_summary(real_text)

        allowed_genres = [
            "로맨스", "로맨스판타지", "현대판타지", "판타지", "무협",
            "헌터/게이트", "회귀", "빙의", "환생", "이세계",
            "대체역사", "역사", "추리/미스터리", "스릴러", "공포",
            "SF", "드라마", "코미디", "액션", "모험", "전쟁",
            "정치", "의학", "성장", "학원", "서바이벌", "디스토피아"
        ]
        genre: List[str] = ["드라마"]

        if self.llm is not None:
            prompt = f"""
너는 웹소설 편집자다. 아래 글을 읽고 장르를 추측해라.
[규칙]
- 출력은 JSON만
- 키는 "genre" 하나만 (리스트)
- 반드시 후보에서만 선택
- 최소 1개, 최대 3개
- 후보: {allowed_genres}

[텍스트]
{real_text[:3500]}
"""
            try:
                res = self.llm.invoke(prompt)
                raw = getattr(res, "content", str(res))
                data = self._safe_json(raw) or {}
                g = data.get("genre", [])

                if isinstance(g, str) and g.strip():
                    g_list = [g.strip()]
                elif isinstance(g, list):
                    g_list = [str(x).strip() for x in g if str(x).strip()]
                else:
                    g_list = []

                # 필터링
                allowed = set(allowed_genres)
                cleaned = []
                for x in g_list:
                    if x in allowed and x not in cleaned:
                        cleaned.append(x)

                genre = cleaned[:3] if cleaned else ["드라마"]
            except Exception:
                pass

        # 3. 데이터 저장
        current_data = _read_json(self.global_setting_file, default={})
        current_data["summary"] = summary
        current_data["genre"] = genre

        try:
            _write_json(self.global_setting_file, current_data)
            print(f"🌍 [세계관 설정] 업데이트 완료: {self.global_setting_file}")
            return {"status": "success", "data": current_data}
        except Exception as e:
            print(f"🔥 [세계관 설정] 저장 실패: {e}")
            return {"status": "error", "message": str(e)}

    # ---------------------------------------------------------
    # (기존 기능) 에피소드 요약 및 히스토리 저장
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # (기존 기능) 파이프라인용 팩트 추출
    # ---------------------------------------------------------
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
            data = self._safe_json(raw) or {}
            if not data:
                return {"episode_no": int(episode_no), "events": [], "characters": [], "state_changes": {}}

            data["episode_no"] = int(episode_no)
            if "events" not in data: data["events"] = []
            if "characters" not in data: data["characters"] = []
            if "state_changes" not in data: data["state_changes"] = {}
            return data
        except Exception:
            return {"episode_no": int(episode_no), "events": [], "characters": [], "state_changes": {}}


class StoryHistoryManager:
    def __init__(self):
        self.pm = PlotManager()

    def summarize_and_save_episode(self, *, episode_no: int, full_text: str) -> Dict[str, Any]:
        return self.pm.summarize_and_save(int(episode_no), full_text)



# =========================================================
# 📢 ingest_service 연결용 함수
# =========================================================
def update_world_setting(text: str) -> Dict[str, Any]:
    """
    PlotManager를 생성하고 설정을 업데이트하는 래퍼 함수.
    ingest_service.py에서 이 함수를 import해서 사용합니다.
    """
    try:
        manager = PlotManager()
        # 이제 인자 하나만 넘겨도 내부에서 처리됨 (호환성 패치 적용됨)
        return manager.update_global_settings(text)
    except Exception as e:
        return {"status": "error", "message": str(e)}
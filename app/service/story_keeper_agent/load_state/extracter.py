# app/service/story_keeper_agent/load_state/extracter.py
import os
import json
from typing import Any, Dict
from datetime import datetime

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()


class PlotManager:
    def __init__(self):
        # SSL_CERT_FILE 깨졌을 때만 certifi로 복구
        self._fix_ssl_cert_env()

        self.llm = ChatUpstage(model="solar-pro")
        self.parser = JsonOutputParser()

        # load_state 폴더
        self.data_dir = os.path.dirname(os.path.abspath(__file__))

        # 프로젝트 루트 기준 app/data/plot.json
        project_root = os.path.abspath(os.path.join(self.data_dir, "../../../../"))
        self.global_setting_file = os.path.join(project_root, "app", "data", "plot.json")

        # 히스토리는 load_state 폴더에 저장
        self.history_file = os.path.join(self.data_dir, "story_history.json")

        print(f"📂 plot.json: {self.global_setting_file}")
        print(f"📂 story_history.json: {self.history_file}")

    def _fix_ssl_cert_env(self) -> None:
        """
        Windows에서 SSL_CERT_FILE이 깨져있으면 httpx가 터질 수 있어서 certifi로 교체.
        """
        try:
            import certifi

            cafile = certifi.where()
            env_path = os.environ.get("SSL_CERT_FILE", "").strip()

            if (not env_path) or (env_path and not os.path.exists(env_path)):
                os.environ["SSL_CERT_FILE"] = cafile

            if not os.environ.get("REQUESTS_CA_BUNDLE", "").strip():
                os.environ["REQUESTS_CA_BUNDLE"] = os.environ["SSL_CERT_FILE"]
            if not os.environ.get("CURL_CA_BUNDLE", "").strip():
                os.environ["CURL_CA_BUNDLE"] = os.environ["SSL_CERT_FILE"]

        except Exception:
            # 없어도 서버 안 죽게
            pass

    def _backup_broken_json(self, path: str):
        try:
            if not os.path.exists(path):
                return
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{path}.broken_{ts}.json"
            os.replace(path, backup_path)
            print(f"⚠️ 깨진 JSON 백업: {backup_path}")
        except Exception:
            pass

    def _read_json(self, path: str, default: Any):
        if not os.path.exists(path):
            return default

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            self._backup_broken_json(path)
            return default
        except Exception:
            return default

    def _write_json(self, path: str, data: Any):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    # =========================
    # 세계관 설정 저장(정리 + 장르 + 중요포인트)
    # =========================
    def update_global_settings(self, setting_text: str):
        existing_settings = self._read_json(self.global_setting_file, default={})
        if not isinstance(existing_settings, dict):
            existing_settings = {}

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 웹소설 '세계관 관리자'입니다.
입력된 세계관을 '요약'이 아니라 '정리'에 가깝게 구조화해서 저장합니다.

중요:
- 원고(회차 내용)나 사건 전개/대사 같은 에피소드성 내용은 저장하지 마세요.
- 세계관/작품 전제/장르/핵심 설정만 남기세요.
- 너무 짧게 줄이지 말고, 읽으면 작품 전제가 이해되게 정리하세요.

반환은 반드시 JSON만.
출력 JSON 키는 정확히 아래 3개만 사용:
1) summary: 세계관 정리(여러 문장/항목형 가능). 거의 요약하지 말고 정리 느낌으로.
2) genre: AI가 판단한 장르 1~2개 (예: 대체역사, 의학, 회귀 등)
3) important_parts: 고증/설정 불일치 방지 위해 반드시 지켜야 할 핵심 포인트 5~10개 (문장 리스트)

[기존 저장된 세계관(있으면 참고)]
{existing_settings}
""",
                ),
                ("human", "세계관 설정 입력:\n{input}"),
            ]
        )

        chain = prompt | self.llm | self.parser
        result = chain.invoke(
            {
                "input": setting_text,
                "existing_settings": json.dumps(existing_settings, ensure_ascii=False),
            }
        )

        if not isinstance(result, dict):
            result = {}

        summary = str(result.get("summary", "") or "")
        genre = str(result.get("genre", "") or "")
        important_parts = result.get("important_parts", [])
        if not isinstance(important_parts, list):
            important_parts = []

        cleaned = {
            "summary": summary,
            "genre": genre,
            "important_parts": [str(x) for x in important_parts if str(x).strip()],
        }

        self._write_json(self.global_setting_file, cleaned)

        return {
            "status": "success",
            "message": "세계관(plot.json) 저장 완료",
            "data": cleaned,
        }

    # =========================
    # full_text 요약 -> story_history.json 저장
    # (episode_no, title, summary, story_flow)
    # =========================
    def summarize_and_save(self, episode_no: int, full_text: str) -> Dict[str, Any]:
        if not isinstance(episode_no, int) or episode_no < 1:
            return {"status": "error", "message": "episode_no는 1 이상의 정수여야 합니다."}
        if not isinstance(full_text, str) or not full_text.strip():
            return {"status": "error", "message": "full_text가 비어있습니다."}

        history_data = self._read_json(self.history_file, default={})
        if not isinstance(history_data, dict):
            history_data = {}

        prev_flow = ""
        if str(episode_no - 1) in history_data and isinstance(history_data[str(episode_no - 1)], dict):
            prev_flow = str(history_data[str(episode_no - 1)].get("story_flow", ""))

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 웹소설 편집자입니다.
목표는 '회차 간 흐름을 관리하기 위한 요약 기록'을 만드는 것입니다.

주의:
- 설정 오류, 떡밥, 문제점은 작성하지 마세요.
- 디테일한 문장 표현은 생략하세요.
- 오직 '무슨 일이 일어났는지'와 '이 화의 역할'만 작성합니다.

반환은 반드시 JSON만.
출력 JSON 키는 정확히 아래 3개만 사용:
1) title: 이번 화를 대표하는 회차 제목(짧고 명확하게)
2) summary: 이번 화 핵심 사건 요약(3~4문장)
3) story_flow: 전체 이야기에서 이 화의 역할(1문장)

[이전 화 흐름]
{prev_flow}
""",
                ),
                ("human", "이번 화 원고:\n{input}"),
            ]
        )

        try:
            result = (prompt | self.llm | self.parser).invoke({"input": full_text, "prev_flow": prev_flow})
            if not isinstance(result, dict):
                result = {}

            history_data[str(episode_no)] = {
                "episode_no": episode_no,
                "title": str(result.get("title", "") or ""),
                "summary": str(result.get("summary", "") or ""),
                "story_flow": str(result.get("story_flow", "") or ""),
            }

            self._write_json(self.history_file, history_data)

            return {
                "status": "success",
                "message": "story_history.json 요약 저장 완료",
                "data": history_data[str(episode_no)],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================
    # full_text -> episode_facts 추출 (rules 엔진 입력용)
    # =========================
    def extract_facts(self, episode_no: int, full_text: str, story_state: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(episode_no, int) or episode_no < 1:
            return {"episode_no": episode_no, "events": [], "characters": [], "state_changes": {}}
        if not isinstance(full_text, str) or not full_text.strip():
            return {"episode_no": episode_no, "events": [], "characters": [], "state_changes": {}}

        global_settings = self._read_json(self.global_setting_file, default={})
        if not isinstance(global_settings, dict):
            global_settings = {}

        history_data = self._read_json(self.history_file, default={})
        if not isinstance(history_data, dict):
            history_data = {}

        prev_summary = ""
        if str(episode_no - 1) in history_data and isinstance(history_data[str(episode_no - 1)], dict):
            prev_summary = str(history_data[str(episode_no - 1)].get("summary", ""))

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 웹소설 편집 보조 AI입니다.
이번 화 원고에서 '규칙 엔진이 검사할 수 있는' 사실들을 구조화하세요.

규칙:
- evidence에는 가능하면 원문 일부를 짧게 넣기
- events는 사건(행동/발생/사용/이동 등)
- characters는 인물별 행동(actions)과 선택(decisions)
- state_changes는 다음 화로 이어질 상태 변화

[세계관/설정(plot.json)]
{global_settings}

[이전 요약]
{prev_summary}

[현재 누적 상태(story_state)]
{story_state}

반환은 반드시 JSON만.
출력 JSON 구조(키 이름은 고정):
- episode_no: int
- events: list
- characters: list
- state_changes: dict
""",
                ),
                ("human", "이번 화 원고:\n{input}"),
            ]
        )

        try:
            result = (prompt | self.llm | self.parser).invoke(
                {
                    "input": full_text,
                    "global_settings": json.dumps(global_settings, ensure_ascii=False),
                    "prev_summary": prev_summary,
                    "story_state": json.dumps(story_state, ensure_ascii=False),
                }
            )

            if not isinstance(result, dict):
                return {"episode_no": episode_no, "events": [], "characters": [], "state_changes": {}}

            result.setdefault("episode_no", episode_no)

            if not isinstance(result.get("events"), list):
                result["events"] = []
            if not isinstance(result.get("characters"), list):
                result["characters"] = []
            if not isinstance(result.get("state_changes"), dict):
                result["state_changes"] = {}

            return result
        except Exception:
            return {"episode_no": episode_no, "events": [], "characters": [], "state_changes": {}}

import os
import json
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()


class PlotManager:
    def __init__(self):
        self.llm = ChatUpstage(model="solar-pro")
        self.parser = JsonOutputParser()

        # ✅ load_state 폴더 자체를 저장소로 사용
        self.data_dir = os.path.dirname(os.path.abspath(__file__))

        print(f"📂 [StoryKeeper] 데이터 저장 경로: {self.data_dir}")

        self.global_setting_file = os.path.join(self.data_dir, "../../../data/plot.json")
        self.history_file = os.path.join(self.data_dir, "story_history.json")

    def _read_json(self, path: str, default: Any):
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: str, data: Any):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    # =========================
    # [기능 1] 세계관 설정 저장
    # =========================
    def update_global_settings(self, setting_text: str):
        existing_settings = self._read_json(self.global_setting_file, default={})

        print("🌍 [설정] 세계관 업데이트 중...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 웹소설 '세계관 관리자'입니다.
    입력된 내용을 바탕으로 '세계관'만 구조화하여 JSON으로 반환하세요.
    ※ 캐릭터/플롯/사건/에피소드 내용은 절대 저장하지 않습니다.

    [출력 형식]
    {{
      "world_rules": {{
        "magic_allowed": true,
        "curfew": null
      }},
      "world_background": "배경 설명",
      "world_keywords": ["키워드1", "키워드2"]
    }}

    [기존 세계관 설정]
    {existing_settings}
    """),
            ("human", "세계관 설정 입력: {input}")
        ])

        chain = prompt | self.llm | self.parser
        result = chain.invoke({
            "input": setting_text,
            "existing_settings": json.dumps(existing_settings, ensure_ascii=False)
        })

        # ✅ plot.json에는 세계관만 저장
        self._write_json(self.global_setting_file, result)
        return {"status": "success", "message": "세계관(plot.json) 저장 완료", "data": result}

    # ==========================================
    # ✅ [기능 2] full_text 요약 -> story_history.json 저장
    # ==========================================
    def summarize_and_save(self, episode_no: int, full_text: str) -> Dict[str, Any]:
        if not isinstance(episode_no, int) or episode_no < 1:
            return {"status": "error", "message": "episode_no는 1 이상의 정수여야 합니다."}
        if not isinstance(full_text, str) or not full_text.strip():
            return {"status": "error", "message": "full_text가 비어있습니다."}

        global_settings = self._read_json(self.global_setting_file, default={})
        history_data = self._read_json(self.history_file, default={})

        prev_flow = ""
        if str(episode_no - 1) in history_data:
            prev_flow = history_data[str(episode_no - 1)].get("story_flow", "")

        print(f"🧾 [요약] {episode_no}화 요약(흐름 중심) 저장 중...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 웹소설 편집자입니다.
    목표는 '회차 간 흐름을 관리하기 위한 요약 기록'을 만드는 것입니다.

    ⚠️ 주의:
    - 설정 오류, 떡밥, 문제점은 작성하지 마세요.
    - 디테일한 감정 묘사, 문장 표현은 생략하세요.
    - 오직 '무슨 일이 일어났는지'와 '이 화의 역할'만 작성합니다.

    [요약 작성 기준]
    1) summary:
       - 이 화에서 실제로 발생한 핵심 사건만 3~4문장으로 요약
    2) story_flow:
       - 이 화가 전체 이야기 흐름에서 가지는 의미를 1문장으로 정리
       - (도입/전환/갈등 심화/클라이맥스 준비 등)

    [이전 화 흐름]
    {prev_flow}

    [출력 형식]
    {{
      "summary": "이번 화 핵심 사건 요약",
      "story_flow": "전체 이야기에서 이 화의 역할"
    }}
    """),
            ("human", "이번 화 원고:\n{input}")
        ])

        try:
            result = (prompt | self.llm | self.parser).invoke({
                "input": full_text,
                "prev_flow": prev_flow
            })

            # ✅ history에는 오직 summary + story_flow만 저장
            history_data[str(episode_no)] = {
                "summary": result.get("summary", ""),
                "story_flow": result.get("story_flow", "")
            }

            self._write_json(self.history_file, history_data)

            return {
                "status": "success",
                "message": "story_history.json 요약 저장 완료",
                "data": history_data[str(episode_no)]
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==========================================
    # ✅ [기능 3] full_text -> episode_facts 추출 (rules 엔진 입력용)
    # ==========================================
    def extract_facts(self, episode_no: int, full_text: str, story_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        check_consistency()에 넣을 episode_facts를 생성한다.

        반환 형태(최소 고정):
        {
          "episode_no": int,
          "events": [{"type": "...", "evidence": "..."}],
          "characters": [{"name": "...", "actions":[{"uses":"...", "evidence":"..."}], "decisions":[...]}],
          "state_changes": {...}
        }
        """
        if not isinstance(episode_no, int) or episode_no < 1:
            return {"episode_no": episode_no, "events": [], "characters": [], "state_changes": {}}
        if not isinstance(full_text, str) or not full_text.strip():
            return {"episode_no": episode_no, "events": [], "characters": [], "state_changes": {}}

        global_settings = self._read_json(self.global_setting_file, default={})
        history_data = self._read_json(self.history_file, default={})

        prev_summary = ""
        if str(episode_no - 1) in history_data and isinstance(history_data[str(episode_no - 1)], dict):
            prev_summary = str(history_data[str(episode_no - 1)].get("summary", ""))

        # world_rules / character_config / plot_config를 story_state에서 최대한 꺼내되,
        # 현재 프로젝트 구조가 정해지지 않았으니 안전하게 기본값 처리
        world_rules = story_state.get("world_rules")
        if world_rules is None:
            # plot.json이 {"world_view": {"rules": ...}} 형태면 rules를 world_rules로도 제공
            world_view = global_settings.get("world_view", {}) if isinstance(global_settings, dict) else {}
            world_rules = world_view.get("rules", [])

        print(f"🧩 [Facts] {episode_no}화 episode_facts 추출 중...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 웹소설 편집 보조 AI입니다.
아래 정보를 참고하여 이번 화 원고에서 '규칙 엔진이 검사할 수 있는' 사실들을 구조화하세요.

- events: 사건(행동/발생/사용/이동 등). type은 간단한 snake_case.
- characters: 인물별 행동(actions)과 선택(decisions). 가능한 경우 evidence에 원문 일부를 넣기.
- state_changes: 다음 화로 이어질 상태 변화(소지품, 관계, 부상/상태, 위치 등)

[세계관/설정]
{global_settings}

[이전 요약]
{prev_summary}

[현재 누적 상태(story_state)]
{story_state}

[출력 JSON 형식]
{{
  "episode_no": {episode_no},
  "events": [
    {{ "type": "travel|fight|magic_use|discover|dialogue|...", "evidence": "원문 일부" }}
  ],
  "characters": [
    {{
      "name": "인물명",
      "actions": [
        {{ "uses": "left_arm|right_arm|weapon|magic|...", "evidence": "원문 일부" }}
      ],
      "decisions": [
        {{ "type": "kill|betray|help|hide|confess|...", "target": "대상", "evidence": "원문 일부" }}
      ]
    }}
  ],
  "state_changes": {{
    "inventory": ["획득한 아이템"],
    "characters": {{
      "인물명": {{ "injury": "left_arm_broken|...", "location": "장소", "status": "..." }}
    }},
    "notes": ["중요 정보/단서"]
  }}
}}
"""),
            ("human", "이번 화 원고: {input}")
        ])

        try:
            result = (prompt | self.llm | self.parser).invoke({
                "input": full_text,
                "global_settings": json.dumps(global_settings, ensure_ascii=False),
                "prev_summary": prev_summary,
                "story_state": json.dumps(story_state, ensure_ascii=False),
                "episode_no": episode_no,
            })

            # ✅ 최소 형태 보정(LLM 출력이 이상해도 rules가 안 죽게)
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
            # 실패해도 서버가 죽지 않게 최소 구조 반환
            return {"episode_no": episode_no, "events": [], "characters": [], "state_changes": {}}

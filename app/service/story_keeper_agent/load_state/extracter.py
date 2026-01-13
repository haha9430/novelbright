import os
import json
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()


class PlotManager:
    def __init__(self):
        self.llm = ChatUpstage(model="solar-pro")
        self.parser = JsonOutputParser()

        # ✅ 파일이 위치한 폴더를 데이터 저장소로 사용
        self.data_dir = os.path.dirname(os.path.abspath(__file__))
        self.global_setting_file = os.path.join(self.data_dir, "plot.json")
        self.history_file = os.path.join(self.data_dir, "story_history.json")

        print(f"📂 [StoryKeeper] 데이터 저장 경로: {self.data_dir}")

    def _read_json(self, path: str, default: Any):
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: str, data: Any):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    # ==========================================
    # [기능 1] 세계관 데이터 업데이트 (plot.json)
    # ==========================================
    def update_global_settings(self, setting_text: str):
        existing_settings = self._read_json(self.global_setting_file, default={})

        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 웹소설 세계관 데이터 관리자입니다.
입력된 내용을 바탕으로 [세계관/캐릭터/설정] 데이터를 구조화하여 JSON으로 반환하세요.
감상이나 제언은 배제하고 오직 정의된 속성값만 추출합니다.

[출력 형식]
{{
  "characters": [{{ "name":"이름", "features":"특징", "role":"역할" }}],
  "world_view": {{ "rules": ["규칙"], "background": "배경" }},
  "main_conflict": "핵심 갈등"
}}

[기존 설정]
{existing_settings}
"""),
            ("human", "설정 입력: {input}")
        ])

        chain = prompt | self.llm | self.parser
        result = chain.invoke({
            "input": setting_text,
            "existing_settings": json.dumps(existing_settings, ensure_ascii=False)
        })

        self._write_json(self.global_setting_file, result)
        return {"status": "success", "message": "세계관 데이터 업데이트 완료", "data": result}

    # ==========================================
    # [기능 2] 원고 분석 및 논리 정합성 검증
    # ==========================================
    def summarize_and_save(self, episode_no: int, full_text: str) -> Dict[str, Any]:
        """
        원고를 분석하여 객관적 사실과 설정 데이터 간의 정합성만 추출합니다.
        축약 호칭(성/이름 생략)은 정상 데이터로 간주하여 보고하지 않습니다.
        """
        if not isinstance(episode_no, int) or episode_no < 1:
            return {"status": "error", "message": "episode_no는 1 이상의 정수여야 합니다."}

        global_settings = self._read_json(self.global_setting_file, default={})
        if not global_settings:
            return {"status": "error", "message": "기준 설정 데이터(plot.json)가 없습니다."}

        history_data = self._read_json(self.history_file, default={})

        prev_summary = ""
        if str(episode_no - 1) in history_data:
            prev_summary = str(history_data[str(episode_no - 1)].get("summary", ""))

        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 웹소설 '설정 데이터 검증기'입니다.
시대 고증, 주관적 제언, 독자 반응은 완전히 무시하고 아래 지침에 따라 '명백한 설정 모순'만 추출하세요.

1) summary: 이번 화에서 발생한 물리적 사건 위주의 팩트 요약 (3~5문장). 감정 묘사 배제.
2) major_changes: 인물의 위치 변화, 신분 상태 변경, 새로운 아이템/정보 습득 등 DB 업데이트용 값.
3) consistency_issues: [세계관/설정] 데이터와 원고 내용이 명백히 충돌하는 경우만 작성.
   - [호칭 규칙]: 설정된 풀네임(예: 조지프 리스터)의 일부(예: 조지프, 리스터)를 부르는 것은 100% 정상이므로 절대 오류로 기록하지 말 것.
   - [오류 판단 기준]: 설정에 없는 다른 이름으로 불리거나, 설정된 캐릭터의 성격/능력이 근거 없이 붕괴되거나, 설정된 장소의 특징이 파괴된 경우만 기록.
   - 축약어임을 인지했다면 해당 항목은 빈 리스트([])로 처리할 것.

[세계관/설정]
{global_settings}

[이전 줄거리]
{prev_summary}

[출력 형식]
{{
  "summary": "객관적 사실 요약",
  "major_changes": ["상태값 변경 내역"],
  "consistency_issues": ["명백한 설정 충돌 내역 (없으면 [])"]
}}
"""),
            ("human", "이번 화 원고: {input}")
        ])

        try:
            result = (prompt | self.llm | self.parser).invoke({
                "input": full_text,
                "global_settings": json.dumps(global_settings, ensure_ascii=False),
                "prev_summary": prev_summary
            })

            # 결과 저장
            history_data[str(episode_no)] = result
            self._write_json(self.history_file, history_data)

            return {
                "status": "success",
                "message": f"{episode_no}화 데이터 분석 완료",
                "data": result
            }

        except Exception as e:
            return {"status": "error", "message": f"분석 중 예외 발생: {str(e)}"}
from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests

from dotenv import load_dotenv

load_dotenv()

class SolarClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("SOLAR_API_KEY", "").strip()
        self.base_url = os.getenv("SOLAR_BASE_URL", "https://api.upstage.ai/v1/chat/completions").strip()
        self.model = os.getenv("SOLAR_MODEL", "solar-pro").strip()

    def parse_character(self, text: str) -> Dict[str, Any]:
        """
        [수정됨] DB 스키마(job_status, age_gender 등)에 맞춰 캐릭터 정보를 추출합니다.
        """
        if not text or not text.strip():
            raise ValueError("text is empty")

        if not self.api_key or not self.base_url:
            raise RuntimeError(
                "Solar 설정이 없습니다. 환경변수 SOLAR_API_KEY, SOLAR_BASE_URL을 설정하세요."
            )

        # ✅ [핵심 수정] DB에 저장되는 키 이름과 100% 일치시켰습니다.
        schema_instruction = {
            "name": "string (이름)",
            "age_gender": "string (나이와 성별 서술, 예: '20대 남성')",
            "job_status": "string (직업 또는 신분)",
            "core_traits": ["string", "string", "string"], # 핵심 특징 3가지
            "personality": {
                "pros": "string (성격의 장점)",
                "cons": "string (성격의 단점)"
            },
            "outer_goal": "string (외적 목표)",
            "inner_goal": "string (내적 목표)",
            "trauma_weakness": "string (트라우마 또는 약점)",
            "speech_habit": "string (말버릇)",
            "relationships": [
                {"target_name": "string", "type": "string", "summary": "string"}
            ],
            "additional_settings": {}
        }

        system_prompt = (
            "너는 웹소설 캐릭터 설정을 정리하는 전문 편집자다.\n"
            "사용자가 제공한 텍스트를 분석해, 반드시 아래 JSON 양식에 맞춰 정보를 추출하라.\n\n"
            "[작업 규칙]\n"
            "1. 출력 포맷: 오직 JSON 데이터만 출력할 것 (마크다운, 설명 금지).\n"
            "2. 빈 값 처리: 텍스트에 정보가 없으면 'none' 문자열을 넣을 것 (빈 칸으로 두지 말 것).\n"
            "3. 리스트: 'core_traits'는 가능한 3개로 채우고, 없으면 빈 리스트 []로 둘 것.\n"
            "4. 성격: 'personality'는 pros(장점)와 cons(단점) 필드를 가진 객체로 만들 것.\n"
            "5. 키 이름 준수: 아래 스키마의 키 이름을 정확히 지킬 것.\n\n"
            f"Target JSON Schema:\n{json.dumps(schema_instruction, ensure_ascii=False)}"
        )

        user_prompt = f"캐릭터 설명 텍스트:\n{text}"

        content = self._request(system_prompt, user_prompt)
        content = self._strip_code_fences(content)
        content = self._extract_json_object(content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # 파싱 실패 시 로그를 남기거나 에러 처리
            print(f"⚠️ JSON 파싱 실패. 원본 응답:\n{content}")
            raise ValueError(f"Solar output is not valid JSON: {e}")

    def parse_command(self, text: str) -> Dict[str, Any]:
        """
        (추가 기능) 사용자의 입력(text)이
        - create(신규 추가)
        - update(수정)
        - delete(삭제)
        중 무엇인지 판단해서 '명령 JSON'을 반환한다.

        반환 형식(반드시 JSON만):
        {
          "action": "create|update|delete",
          "target": {"id": null|string, "name": null|string},
          "payload": {...},   # create일 때만
          "patch": {...},     # update일 때만
          "reason": "짧게"
        }
        """
        if not text or not text.strip():
            raise ValueError("text is empty")

        if not self.api_key or not self.base_url:
            raise RuntimeError(
                "Solar 설정이 없습니다. 환경변수 SOLAR_API_KEY, SOLAR_BASE_URL을 설정하세요."
            )

        # create용 payload 스키마(참고)
        character_payload_schema = {
            "name": "string",
            "birthdate_or_age": "string",
            "gender": "string",
            "occupation": "string",
            "core_features": ["string", "string", "string"],
            "personality_strengths": ["string", "string", "string"],
            "personality_weaknesses": ["string", "string", "string"],
            "external_goal": "string",
            "internal_goal": "string",
            "trauma_weakness": "string",
            "speech_habit": "string",
            "relationships": [
                {"target_name": "string", "type": "string", "summary": "string"}
            ],
            "additional_settings": {}
        }

        # command 스키마(고정)
        command_schema = {
            "action": "create|update|delete",
            "target": {"id": None, "name": None},
            "payload": {},
            "patch": {},
            "reason": "string"
        }

        system_prompt = (
            "너는 웹소설 총괄 편집자이자 데이터 정리 도우미다.\n"
            "사용자 입력은 다음 중 하나일 수 있다:\n"
            "- 신규 등장인물 추가(create)\n"
            "- 기존 등장인물 정보 수정(update)\n"
            "- 기존 등장인물 삭제(delete)\n\n"
            "반드시 JSON만 출력하라(설명/문장/마크다운 금지).\n"
            "아래 스키마 형태로만 출력:\n"
            f"{json.dumps(command_schema, ensure_ascii=False)}\n\n"
            "판단 규칙:\n"
            "1) 등장인물의 상세 묘사/소개가 중심이면 create\n"
            "2) '바꿔', '수정', '변경', '추가로 넣어', '업데이트' 등 변경 의도가 있으면 update\n"
            "3) '삭제', '지워', '제거' 등 제거 의도가 있으면 delete\n"
            "4) target은 가능하면 id를 채우고, 없으면 name을 채워라\n"
            "5) create일 때만 payload에 캐릭터 정보를 채워라\n"
            "6) update일 때는 patch에 '변경할 필드만' 넣어라(변경 없는 필드는 넣지 마라)\n"
            "7) delete일 때는 payload/patch는 빈 객체로 둬라\n\n"
            "create payload는 아래 스키마를 참고해 채워라:\n"
            f"{json.dumps(character_payload_schema, ensure_ascii=False)}"
        )

        user_prompt = f"사용자 입력:\n{text}"

        content = self._request(system_prompt, user_prompt)
        content = self._strip_code_fences(content)
        content = self._extract_json_object(content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Solar output is not valid JSON: {e}\nRaw: {content}")

    def _request(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return self._extract_content(data)

    def _extract_content(self, data: Dict[str, Any]) -> str:
        if "choices" in data and data["choices"]:
            msg = data["choices"][0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                return content
        return json.dumps(data, ensure_ascii=False)

    def _strip_code_fences(self, s: str) -> str:
        s = (s or "").strip()

        # ```json ... ``` 또는 ``` ... ``` 제거
        if s.startswith("```"):
            lines = s.splitlines()
            # 첫 줄: ```json 또는 ```
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # 마지막 줄: ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            s = "\n".join(lines).strip()

        return s

    def _extract_json_object(self, s: str) -> str:
        """
        content에 설명문이 섞여도 JSON 객체({ ... })만 뽑아내기.
        """
        s = (s or "").strip()
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return s[start:end + 1]
        return s

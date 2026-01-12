# app/service/history/history_client.py
from __future__ import annotations
import json
import os
import requests
from typing import Any, Dict
from dotenv import load_dotenv

load_dotenv()

class HistoryLLMClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("SOLAR_API_KEY", "").strip()
        self.base_url = os.getenv("SOLAR_BASE_URL", "https://api.upstage.ai/v1/chat/completions").strip()
        self.model = os.getenv("SOLAR_MODEL", "solar-pro").strip()

    def parse_history_command(self, text: str) -> Dict[str, Any]:
        """
        사용자 입력을 분석하여 역사 DB에 대한 Action(create/update/delete)과 데이터를 생성
        """
        if not self.api_key:
            raise RuntimeError("SOLAR_API_KEY 환경변수가 필요합니다.")

        # 1. 출력 스키마 정의 (LLM이 이 형식대로 뱉게 유도)
        entity_schema = {
            "name": "string (역사적 사건/인물 명칭)",
            "entity_type": "Event | Person | Artifact | Location | Concept",
            "era": "string (연도 또는 시기)",
            "summary": "string (한 줄 요약)",
            "description": "string (상세 설명)",
            "tags": ["string", "string"],
            "related_entities": [
                {"target_name": "string", "relation_type": "string", "description": "string"}
            ]
        }

        command_schema = {
            "action": "create | update | delete",
            "target": {"id": None, "name": "string (대상 명칭)"},
            "payload": entity_schema, # create용
            "patch": {},              # update용 (변경된 필드만)
            "reason": "string (판단 근거)"
        }

        # 2. 프롬프트 작성
        system_prompt = (
            "너는 엄격한 '역사 아카이브 관리자'다.\n"
            "사용자가 입력한 역사적 텍스트를 분석하여 데이터베이스 관리 명령(JSON)으로 변환하라.\n\n"
            "규칙:\n"
            "1. **JSON 포맷 준수**: 설명 없이 오직 JSON 객체만 출력하라.\n"
            "2. **Action 판단**:\n"
            "   - 새로운 역사적 사실 서술 -> 'create'\n"
            "   - 기존 내용의 수정, 정정, 보완 -> 'update'\n"
            "   - 삭제 요청 -> 'delete'\n"
            "3. **Entity Type**: Event(사건), Person(인물), Artifact(유물), Location(장소) 중 택 1.\n"
            f"4. **출력 스키마**:\n{json.dumps(command_schema, ensure_ascii=False)}"
        )

        user_prompt = f"사용자 입력:\n{text}"

        # 3. API 호출
        response_text = self._request(system_prompt, user_prompt)

        # 4. 후처리 (JSON 파싱)
        cleaned_text = self._strip_code_fences(response_text)
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # 실패 시 로깅하거나 재시도하는 로직이 들어갈 수 있음
            raise ValueError(f"LLM 응답이 유효한 JSON이 아닙니다:\n{cleaned_text}")

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
            "temperature": 0.1, # 정확성을 위해 낮춤
        }

        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _strip_code_fences(self, s: str) -> str:
        s = s.strip()
        if s.startswith("```"):
            lines = s.splitlines()
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].strip() == "```": lines = lines[:-1]
            return "\n".join(lines).strip()
        return s
import json
import re
from typing import List, Dict, Any, Set
from langchain_upstage import ChatUpstage
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

# [변경] VectorService 대신 방금 만든 Repo 임포트
from app.service.manuscript.repo import ManuscriptRepository

class ManuscriptAnalyzer:
    # [변경] 초기화 시 repo를 주입받거나 내부에서 생성
    def __init__(self, setting_path: str):
        self.llm = ChatUpstage(model="solar-pro")
        self.settings = self._load_settings(setting_path)
        self.setting_keywords = self._extract_setting_keywords()

        # [변경] 임시 Repo 직접 연결
        self.repo = ManuscriptRepository()

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def _load_settings(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _extract_setting_keywords(self) -> Set[str]:
        keywords = set()
        data = self.settings
        for char in data.get("characters", []):
            keywords.add(char["name"])
        factions = data.get("world_view", {}).get("factions", [])
        for f in factions:
            keywords.add(f.split("(")[0].strip())
        keywords.add("벽력")
        keywords.add("이매망량")
        return keywords

    def analyze_manuscript(self, text: str) -> Dict[str, Any]:
        print(f"📄 원고 분석 시작 (총 {len(text)}자)")
        chunks = self.text_splitter.split_text(text)

        all_entities = set()
        for i, chunk in enumerate(chunks):
            # (로그 너무 많으면 줄여도 됨)
            entities = self._extract_entities_from_text(chunk)
            all_entities.update(entities)

        known_settings = []
        unknown_terms = []

        for entity in all_entities:
            if entity in self.setting_keywords or any(k in entity for k in self.setting_keywords):
                known_settings.append(entity)
            else:
                unknown_terms.append(entity)

        history_context = []
        if unknown_terms:
            print(f"🔍 역사 DB 조회 시도: {unknown_terms}")
            for term in unknown_terms:
                search_result = self.repo.search(query_text=term, n_results=1)

                # ChromaDB 결과 분해
                documents = search_result.get("documents", [[]])[0]
                distances = search_result.get("distances", [[]])[0]  # [추가] 거리 점수 가져오기

                # [중요] 임계값(Threshold) 설정
                # 거리가 가까울수록 0에 가깝습니다. (L2 거리 기준)
                # 모델마다 다르지만, 보통 1.2 이상이면 "다른 내용"일 확률이 높습니다.
                DISTANCE_THRESHOLD = 1.2

                if documents and distances:
                    doc_content = documents[0]
                    dist = distances[0]

                    # 디버깅용 로그: 실제로 거리가 얼마 나오는지 확인해보세요!
                    print(f"   👉 '{term}' 검색 결과 거리: {dist:.4f}")

                    if dist < DISTANCE_THRESHOLD:
                        history_context.append(f"[{term}]: {doc_content}")
                    else:
                        print(f"      ❌ 거리가 너무 멀어 제외됨 ({dist:.4f} >= {DISTANCE_THRESHOLD})")

        return {
            "found_entities_count": len(all_entities),
            "setting_terms_found": known_settings,
            "historical_terms_searched": unknown_terms,
            "retrieved_history_context": history_context
        }

    def _extract_entities_from_text(self, text: str) -> List[str]:
        # (프롬프트는 아까 수정한 한국어 버전 그대로 사용)
        prompt = """
        당신은 역사 소설의 고증을 돕는 전문 어시스턴트입니다.
        주어진 텍스트에서 '역사적 배경 지식'이나 '백과사전 검색'이 필요한 **중요 키워드(고유명사)**만 추출하세요.

        [추출 규칙]
        1. **대상 (포함):** - 실존했던 역사적 인물
           - 구체적인 지명이나 기관명
           - 특정 지명
           - 역사적 사건, 유물, 종교/학술 용어

        2. **제외 (무시 - 엄격 적용):** - **일반 명사 단독 사용:** 앞뒤에 고유한 이름이 없는 경우 제외.
            - **단순 시공간 표현:** 단순 시점이나 장소 제외.
            - **소설 속 허구:** 주인공의 사적인 대화나 행동에서 나오는 잡다한 사물.

        [출력 형식]
        - 결과는 오직 JSON 리스트 형식으로만 반환하세요.
        - 마크다운이나 부연 설명 없이, 오직 ["항목1", "항목2"] 형태만 출력하세요.
        """

        try:
            response = self.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=text[:3000])
            ])
            content = response.content.strip()

            # [수정] 괄호 짝을 맞춰서 정확한 JSON 영역만 추출하는 함수
            def extract_json_list(s):
                start_idx = s.find('[')
                if start_idx == -1: return None

                count = 0
                for i in range(start_idx, len(s)):
                    if s[i] == '[':
                        count += 1
                    elif s[i] == ']':
                        count -= 1

                    # 괄호가 모두 닫혔을 때 (count가 0이 됨)
                    if count == 0:
                        return s[start_idx : i+1]
                return None

            json_str = extract_json_list(content)

            if json_str:
                result = json.loads(json_str)
                return result if isinstance(result, list) else []
            else:
                # 괄호 구조를 못 찾았을 경우, 기존 방식(단순 제거)으로 한 번 더 시도 (보험)
                fallback = content.replace("```json", "").replace("```", "").strip()
                # 마지막에 혹시 짤렸을 수 있으니 닫는 괄호 체크는 생략하고 시도
                return json.loads(fallback) if isinstance(json.loads(fallback), list) else []

        except json.JSONDecodeError:
            print(f"⚠️ JSON 파싱 실패 (내용): {content[:50]}...")
            return []
        except Exception as e:
            print(f"⚠️ 기타 오류: {e}")
            return []
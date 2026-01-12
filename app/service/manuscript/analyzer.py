import json
import time
from typing import List, Dict, Any, Set

# LangChain & AI 관련
from langchain_upstage import ChatUpstage
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.utilities import GoogleSerperAPIWrapper

# 로컬 DB 레포지토리
from app.service.manuscript.repo import ManuscriptRepository

class ManuscriptAnalyzer:
    def __init__(self, setting_path: str):
        # 1. LLM 설정 (Solar-pro)
        self.llm = ChatUpstage(model="solar-pro")

        # 2. 소설 설정(Plot DB) 로드 -> 허구 정보 필터링용
        self.settings = self._load_settings(setting_path)
        self.setting_keywords = self._extract_setting_keywords()

        # 3. 로컬 벡터 DB (기존 지식)
        self.repo = ManuscriptRepository()

        # 4. Web Search 도구 (Serper)
        # gl='kr': 한국 구글, hl='ko': 한국어 인터페이스 (필요시 'en'으로 변경 가능)
        self.search_tool = GoogleSerperAPIWrapper(gl='kr', hl='ko')

        # 5. 텍스트 분할기
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def _load_settings(self, path: str) -> Dict[str, Any]:
        """설정 파일(JSON)을 로드합니다."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ 설정 파일을 찾을 수 없습니다: {path}")
            return {}

    def _extract_setting_keywords(self) -> Set[str]:
        """소설 속 허구의 고유명사(등장인물, 지명 등)를 Set으로 추출"""
        keywords = set()
        data = self.settings

        # 등장인물 이름
        for char in data.get("characters", []):
            name = char.get("name", "").strip()
            if name: keywords.add(name)

        # 세력/단체명
        factions = data.get("world_view", {}).get("factions", [])
        for f in factions:
            if isinstance(f, str):
                keywords.add(f.split("(")[0].strip())

        # (임시) 테스트용 허구 키워드 추가
        keywords.add("에이단")
        keywords.add("에이단 신부")

        return keywords

    def analyze_manuscript(self, text: str) -> Dict[str, Any]:
        """
        [메인 로직]
        1. 텍스트 분할
        2. '검색 쿼리' 생성 (단순 키워드 추출 X)
        3. 필터링 (설정 DB 확인)
        4. 로컬 DB 조회 -> 웹 검색 -> 결과 검증
        """
        print(f"📄 원고 분석 시작 (총 {len(text)}자)")
        chunks = self.text_splitter.split_text(text)

        # 1. 청크별로 검색 쿼리 후보 추출
        all_query_items = {} # 중복 제거를 위해 Dict 사용 {keyword: query_info}

        for i, chunk in enumerate(chunks):
            items = self._extract_search_queries(chunk)
            for item in items:
                kw = item['keyword']
                # 이미 있는 키워드면 덮어쓰거나 무시 (여기선 최신 쿼리로 갱신)
                all_query_items[kw] = item

        print(f"   -> 총 {len(all_query_items)}개의 검색 후보 추출됨")

        known_settings = []     # 소설 설정에 있는 단어 (검색 안 함)
        historical_context = [] # 최종 결과 리스트

        # 2. 후보군 순회 및 처리
        for keyword, item_data in all_query_items.items():
            query_string = item_data['search_query']
            reason = item_data.get('reason', '')

            # [Filter 1] 소설 설정(허구)에 포함되는지 확인
            # 단순 일치뿐만 아니라 부분 일치도 체크 (예: '에이단' in '에이단 신부님')
            is_fiction = False
            for fiction_term in self.setting_keywords:
                if fiction_term in keyword or keyword in fiction_term:
                    is_fiction = True
                    break

            if is_fiction:
                known_settings.append(keyword)
                continue # 검색 스킵

            # [Process] 정보 검색 시작
            print(f"🔍 분석 중: '{keyword}' (Query: {query_string})")

            # Step A: 로컬 DB 확인 (Vector Store)
            local_result = self._check_local_db(keyword)
            if local_result:
                print(f"   ✅ 로컬 DB 발견")
                historical_context.append(local_result)
                continue # 로컬에 있으면 웹 검색 스킵

            # Step B: 웹 검색 (Serper)
            web_data = self._search_web(query_string)
            if web_data:
                # Step C: [NEW] 검색 결과 적합성 검증 (LLM)
                # 검색된 내용이 실제 소설의 시대적 배경/맥락과 맞는지 확인
                verification = self._verify_content_relevance(keyword, query_string, web_data['content'])

                if verification['is_relevant']:
                    web_data['verification_note'] = verification['reason']
                    historical_context.append(web_data)
                    print(f"   🌐 웹 검색 성공 & 검증 통과")
                else:
                    print(f"   🗑️ 검증 탈락: {verification['reason']}")
            else:
                print(f"   ❌ 정보 없음")

            time.sleep(0.5) # API 속도 조절

        return {
            "found_entities_count": len(all_query_items),
            "setting_terms_found": list(set(known_settings)), # 중복 제거
            "historical_context": historical_context
        }

    def _extract_search_queries(self, text: str) -> List[Dict[str, str]]:
        """
        [수정됨] 구체적인 예시를 제거하고 논리적 지시만 남긴 쿼리 생성기
        """
        prompt = """
        당신은 역사 소설 고증을 위한 '검색 쿼리 생성기'입니다.
        주어진 텍스트를 읽고, 역사적 사실 확인이 필요한 항목을 찾아 **구체적인 검색어**로 변환하세요.

        [작업 규칙]
        1. **대상:** 실존 인물, 지명, 사건, 유물, 당시의 문화/제도.
        2. **제외(Strict):** - '의과 대학', '병원', '신부님', '마차' 같은 **수식어 없는 일반 명사 절대 제외**.
           - '19세기', '오늘', '내일', '런던의 거리' 같은 **단순 시공간 묘사 제외**.
           - 주인공의 사적인 행동, 감정 묘사, 대화의 일상적인 소재 제외.
        3. **쿼리 최적화 지침:** - 단순히 본문의 단어를 그대로 쓰지 말고, **검색 엔진이 이해하기 쉬운 형태**로 조합하세요.
           - 인물 이름이 불완전하게 나오면(예: 성만 나오거나 이름만 나올 때), 문맥을 파악해 **전체 이름이나 직업**을 덧붙이세요.
           - 지명이나 고유명사가 모호할 경우, **'역사', '유래', '19세기' 등의 키워드**를 쿼리에 포함시켜 범위를 좁히세요.

        [출력 형식]
        반드시 아래와 같은 **JSON 리스트**만 출력하세요. (마크다운 없이)
        [
            {"keyword": "본문에 나온 원본 단어", "search_query": "최적화된 구글 검색용 쿼리", "reason": "검색이 필요한 이유 요약"}
        ]
        """

        try:
            response = self.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"Text: {text[:3000]}")
            ])
            content = response.content.strip()

            # JSON 파싱
            return self._parse_json_garbage(content)

        except Exception as e:
            print(f"⚠️ 쿼리 생성 에러: {e}")
            return []

    def _check_local_db(self, keyword: str) -> Dict[str, Any]:
        """로컬 벡터 DB 조회"""
        try:
            # 검색
            search_result = self.repo.search(query_text=keyword, n_results=1)

            if not search_result['documents'][0]:
                return None

            dist = search_result['distances'][0][0]
            content = search_result['documents'][0][0]

            # 거리 임계값 (1.2보다 가까워야 관련성 있음)
            if dist < 1.2:
                return {
                    "keyword": keyword,
                    "content": content,
                    "source": "Local History DB",
                    "confidence": round(1 - (dist/2), 2)
                }
            return None
        except Exception:
            return None

    def _search_web(self, query: str) -> Dict[str, Any]:
        """Serper 웹 검색"""
        try:
            # 검색어에 '역사' 키워드가 없다면 추가 (영어/한글 혼용)
            if "역사" not in query and "history" not in query.lower():
                final_query = f"{query} 역사 history"
            else:
                final_query = query

            result_text = self.search_tool.run(final_query)

            if not result_text or len(result_text) < 10:
                return None

            return {
                "keyword": query, # 검색에 쓴 쿼리 저장
                "content": result_text,
                "source": "Web Search (Serper)"
            }
        except Exception:
            return None

    def _verify_content_relevance(self, keyword: str, query: str, content: str) -> Dict[str, Any]:
        """
        [NEW] 검색 결과 검증기
        찾아온 정보가 내가 의도한 맥락(역사적 사실)과 맞는지 LLM이 판별합니다.
        예: '업턴' 검색 결과가 '케이트 업턴(모델)'이면 False 반환.
        """
        prompt = f"""
        당신은 역사 자료 검증관입니다.
        사용자가 '{keyword}'(쿼리: {query})를 검색했고, 아래 결과를 얻었습니다.
        이 결과가 **역사적 사실, 지리, 인물 정보**로서 유의미한지 판단하세요.

        [검색 결과]
        {content[:1000]}

        [판단 기준]
        1. **부적합:** 현대의 연예인(모델, 배우), 쇼핑몰, 단순 사전적 정의, 게임/영화 정보.
        2. **적합:** 역사적 인물, 실제 존재하는 지명, 역사적 사건, 기관의 연혁.

        결과를 JSON으로 반환하세요:
        {{
            "is_relevant": true/false,
            "reason": "판단 이유 한 문장"
        }}
        """
        try:
            response = self.llm.invoke([SystemMessage(content=prompt)])
            return self._clean_json_string(response.content)
        except:
            # 에러 나면 일단 통과 (False Negative 방지)
            return {"is_relevant": True, "reason": "검증 실패(Pass)"}

    def _parse_json_garbage(self, text: str) -> List[Dict]:
        """LLM이 주는 지저분한 JSON 문자열에서 리스트만 추출"""
        try:
            # 마크다운 제거
            text = text.replace("```json", "").replace("```", "").strip()

            # 가장 바깥쪽 대괄호 찾기
            start = text.find('[')
            end = text.rfind(']')
            if start != -1 and end != -1:
                json_str = text[start:end+1]
                return json.loads(json_str)
            return []
        except:
            return []

    def _clean_json_string(self, text: str) -> str:
        """
                [수정됨] 입력이 이미 Dict라면 그대로 반환하고,
                String이라면 JSON 구간만 추출하여 파싱합니다.
                (TypeError 방지용 방어 코드 포함)
                """
        # 1. 입력이 이미 딕셔너리(Dict)라면 파싱할 필요 없이 바로 반환
        if isinstance(text, dict):
            return text

        # 2. 문자열이 아니라면(None 등) 빈 Dict 반환
        if not isinstance(text, str):
            return {}

        try:
            # 3. 마크다운 및 공백 제거
            text = text.replace("```json", "").replace("```", "").strip()

            # 4. 가장 바깥쪽 {} 찾기 (사족 제거)
            start_idx = text.find('{')
            end_idx = text.rfind('}')

            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_str = text[start_idx : end_idx + 1]
                return json.loads(json_str)

            # 5. 괄호가 없으면 전체 파싱 시도
            return json.loads(text)

        except Exception:
            # 파싱 실패 시 빈 딕셔너리 반환
            return {}
import json
import time
import re
from typing import List, Dict, Any, Set
import difflib

# LangChain & AI 관련
from langchain_upstage import ChatUpstage
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.utilities import GoogleSerperAPIWrapper

# 로컬 DB 레포지토리
from app.service.clio_fact_checker_agent.repo import ManuscriptRepository

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

        # LLM에게는 여전히 청크 단위로 줍니다 (토큰 제한 때문)
        chunks = self.text_splitter.split_text(text)

        all_query_items = {}

        for i, chunk in enumerate(chunks):
            items = self._extract_search_queries(chunk)

            for item in items:
                kw = item['keyword']
                origin_snippet = item.get('original_sentence', '')

                # [NEW] 전체 텍스트(text)에서, 현재 커서(current_global_cursor) 이후부터 찾기
                start_idx, end_idx = self._find_exact_position(
                    full_text=text,
                    target_snippet=origin_snippet,
                    start_from=0
                )

                # 검증 로직 시작
                def _is_content_equal(text1, text2):
                    """특수문자/공백 제거 후 내용 일치 여부 확인"""
                    def normalize(s):
                        return re.sub(r'[\s\W_]+', '', s)
                    return normalize(text1) == normalize(text2)

                def _retry_extract_sentence(chunk_text, keyword):
                    """
                    [LLM 재요청] 특정 키워드에 대해 문장 추출만 다시 수행
                    """
                    prompt = f"""
                    당신은 텍스트 분석가입니다.
                    아래 텍스트에서 키워드 '{keyword}'가 포함된 문장을 **토씨 하나 틀리지 말고 그대로** 추출하세요.

                    [규칙]
                    1. 문장이 너무 길면, 키워드 주변 10어절만 잘라서 가져오세요.
                    2. 설명이나 수식어를 붙이지 말고 오직 **본문 내용만** 출력하세요.
                    3. 없으면 'None'이라고만 출력하세요.
                    """

                    try:
                        response = self.llm.invoke([
                            SystemMessage(content=prompt),
                            HumanMessage(content=f"Text: {chunk_text[:3000]}") # 문맥 제공
                        ])
                        result = response.content.strip().strip('"\'')

                        if result == "None" or len(result) < 2:
                            return None
                        return result

                    except Exception as e:
                        print(f"⚠️ 재시도 중 에러: {e}")
                        return None

                is_match_success = False

                if start_idx != -1:
                    actual_found_text = text[start_idx:end_idx]

                    # 1. 완벽 일치하는지 확인
                    if actual_found_text == origin_snippet:
                        is_match_success = True
                    else:
                        # 2. [불일치 발생] -> 정규화(Normalization) 후 재비교
                        # 공백, 줄바꿈, 특수문자를 다 떼고 비교해서 글자 알맹이가 같은지 확인
                        if _is_content_equal(actual_found_text, origin_snippet):
                            print(f"   ⚠️ [보정 성공] 문장은 다르지만 내용은 같습니다.")
                            print(f"       LLM: {repr(origin_snippet)}")
                            print(f"       Raw: {repr(actual_found_text)}")
                            is_match_success = True
                        else:
                            print(f"   ❌ [불일치] 위치는 찾았으나 내용이 너무 다릅니다.")
                            # 여기서 재시도 로직을 수행하거나, 그냥 이 위치를 신뢰할지 결정
                            # 보통 _find_exact_position이 3단계(유사도)까지 갔다면,
                            # 실제로는 맞는 위치일 확률이 높음.

                # 3. [재시도 로직] 위치를 아예 못 찾았거나, 찾았는데 내용이 영 딴판인 경우
                if start_idx == -1 or (start_idx != -1 and not is_match_success):
                    print(f"   🔄 [재시도] '{kw}'에 대한 문장 추출을 다시 시도합니다...")

                    # LLM에게 해당 키워드로 다시 문장을 뽑아달라고 요청 (Retry 함수 호출)
                    new_snippet = _retry_extract_sentence(chunk, kw)

                    if new_snippet:
                        print(f"      -> 재추출된 문장: {new_snippet}")
                        # 다시 위치 찾기 시도
                        start_idx, end_idx = self._find_exact_position(text, new_snippet, 0)

                        if start_idx != -1:
                            print(f"      ✅ 재시도 성공! 위치 찾음.")
                            item['original_sentence'] = new_snippet # 업데이트


                if start_idx != -1:
                    actual_found_text = text[start_idx:end_idx]

                    print(f"   📍 위치 발견: {start_idx} ~ {end_idx} (Keyword: {kw})")
                    print(f"      👉 [검증] 실제 추출된 문장: \"{actual_found_text}\"")

                    item['start_index'] = start_idx
                    item['end_index'] = end_idx
                else:
                    print(f"   ⚠️ 위치 찾기 실패: '{kw}'")
                    item['start_index'] = -1
                    item['end_index'] = -1

                # 이미 있는 키워드면 덮어쓰거나 무시 (여기선 최신 쿼리로 갱신)
                all_query_items[kw] = item



        print(f"   -> 총 {len(all_query_items)}개의 검색 후보 추출됨")

        known_settings = []     # 소설 설정에 있는 단어 (검색 안 함)
        historical_context = [] # 최종 결과 리스트

        # 2. 후보군 순회 및 처리
        for keyword, item_data in all_query_items.items():
            query_string = item_data['search_query']
            reason = item_data.get('reason', '')
            origin_sent = item_data.get('original_sentence', '')

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

            # [Process] 정보 검색 시작
            # Step B: 웹 검색 (Serper)
            web_data = self._search_web(query_string)

            if web_data:
                # Step C: [검증 & 팩트체크]
                # ★ 수정 포인트: 맥락(item_data['reason'])을 같이 넘겨줍니다.
                verification = self._verify_content_relevance(
                    keyword,
                    query_string,
                    web_data['content'],
                    context=origin_sent
                )

                # 1. 자료 자체가 쓸모없는 경우 (예: 동명이인 연예인) -> 버림
                if verification['is_relevant']:
                    web_data['is_relevant'] = True

                    # 2. 자료는 맞는데, 소설 내용과 일치하는가? (팩트체크 결과 저장)
                    # ★ 수정 포인트: True/False 여부를 필터링하지 않고 결과에 '저장'만 합니다.
                    web_data['is_positive'] = verification['is_positive']
                    web_data['reason'] = verification['reason']
                    web_data['original_sentence'] = origin_sent
                    web_data['start_index'] = item_data.get('start_index')
                    web_data['end_index'] = item_data.get('end_index')

                    historical_context.append(web_data)

                    # 로그 출력 (오류 발견 시 눈에 띄게)
                    if verification['is_positive']:
                        print(f"   ✅ 검증 통과: {verification['reason']}")
                    else:
                        print(f"   ⚠️ 고증 오류 의심: {verification['reason']}")

                else:
                    print(f"   🗑️ 관련 없는 자료(검증 탈락): {verification['reason']}")

            time.sleep(0.2)# API 속도 조절

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
        3. **원문 유지(Critical):** - `original_sentence`를 추출할 때, **절대로 문장을 요약하거나 수정하지 마세요.**
           - 조사, 문장 부호, 띄어쓰기까지 **본문 그대로 복사**해야 시스템이 위치를 찾을 수 있습니다.
        4. **쿼리 최적화 지침:** - 단순히 본문의 단어를 그대로 쓰지 말고, **검색 엔진이 이해하기 쉬운 형태**로 조합하세요.
           - 인물 이름이 불완전하게 나오면(예: 성만 나오거나 이름만 나올 때), 문맥을 파악해 **전체 이름이나 직업**을 덧붙이세요.
           - 지명이나 고유명사가 모호할 경우, **'역사', '유래', '19세기' 등의 키워드**를 쿼리에 포함시켜 범위를 좁히세요.

        [출력 형식]
        반드시 아래와 같은 **JSON 리스트**만 출력하세요.
        [
            {
                "keyword": "본문에 나온 핵심 단어",
                "original_sentence": "본문에서 토씨 하나 안 바꾸고 그대로 복사한 문장 전체",
                "search_query": "구글 검색용 쿼리",
                "reason": "검색이 필요한 이유"
            }
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

            # 거리 임계값 (1.0보다 가까워야 관련성 있음)
            if dist < 1.0:
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

    def _verify_content_relevance(self, keyword: str, query: str, content: str, context: str) -> Dict[str, Any]:
        """
        [NEW] 검색 결과 검증 + 팩트체크
        context: 검색을 하게 된 원문 맥락 (예: '조선시대에 감자가 있었는지 확인')
        """
        prompt = f"""
        당신은 역사 소설의 고증을 담당하는 팩트체커입니다.

        [상황]
        작가가 소설을 쓰다가 **"{context}"** 라는 의문을 품고
        '{keyword}'(쿼리: {query})를 검색하여 아래 결과를 얻었습니다.

        [검색 결과]
        {content[:1500]}

        [판단 기준]
        1. **is_relevant (자료 적합성)**: 검색 결과가 '역사/지리/인물' 정보가 맞으면 true. (현대 연예인, 광고면 false)
        2. **is_positive (사실 일치 여부)**: 
           - 검색 결과에 비추어 볼 때, 작가의 의도나 묘사가 역사적 사실과 **일치하거나 가능성이 있으면 true**.
           - 명백한 시대착오(예: 조선시대 커피)거나 **오류라면 false**.
           - 판단이 불가능하면 true(보류)로 처리.

        결과를 JSON으로 반환하세요:
        {{
            "is_relevant": true/false,
            "is_positive": true/false,
            "reason": "판단의 근거 한 문장 (특히 false일 경우 구체적으로)"
        }}
        """
        try:
            response = self.llm.invoke([SystemMessage(content=prompt)])
            return self._clean_json_string(response.content)
        except Exception as e:
            # 에러 나면 일단 통과 (False Negative 방지)
            return {"is_relevant": True, "reason": f"{str(e)}"}

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

    def _find_exact_position(self, full_text, target_snippet, start_from=0):
        """
        [Global Search 통합 버전]
        1단계: 단순 일치 (Exact Match)
        2단계: 정규화 일치 (Regex Normalization) - 공백/특수문자 무시
        3단계: 유사도 일치 (Fuzzy Match / Difflib) - 오타/변형 대응
        """
        if not target_snippet:
            return -1, -1

        # 검색 범위를 start_from 이후로 제한
        search_scope_text = full_text[start_from:]

        # ---------------------------------------------------------
        # 1단계: 단순 검색 (Exact Match)
        # ---------------------------------------------------------
        clean_target = target_snippet.strip(" '\"\n")
        if not clean_target:
            return -1, -1

        local_idx = search_scope_text.find(clean_target)
        if local_idx != -1:
            real_start = start_from + local_idx
            real_end = real_start + len(clean_target)
            return real_start, real_end

        # ---------------------------------------------------------
        # 2단계: 정규식 기반 유연한 검색 (Normalization)
        # ---------------------------------------------------------
        # 공백, 특수문자를 모두 제거하고 글자(Alphanumeric)만 비교
        def normalize(s):
            return re.sub(r'[\s\W_]+', '', s)

        norm_scope = normalize(search_scope_text)
        norm_target = normalize(clean_target)

        if not norm_target:
            return -1, -1

        norm_idx = norm_scope.find(norm_target)

        if norm_idx != -1:
            # 정제된 인덱스(norm_idx)를 원본 인덱스로 역매핑
            current_norm_pos = 0
            real_local_start = -1
            real_local_end = -1

            for i, char in enumerate(search_scope_text):
                # 원본 문자 중 특수문자/공백은 카운트하지 않고 건너뜀
                if re.match(r'[\s\W_]', char):
                    continue

                # 시작 위치 포착
                if current_norm_pos == norm_idx:
                    real_local_start = i

                # 끝 위치 포착 (길이만큼 진행했을 때)
                if current_norm_pos == norm_idx + len(norm_target) - 1:
                    real_local_end = i + 1
                    break

                current_norm_pos += 1

            if real_local_start != -1 and real_local_end != -1:
                return (start_from + real_local_start), (start_from + real_local_end)

        # ---------------------------------------------------------
        # 3단계: 유사도 기반 검색 (Fuzzy Match - Difflib)
        # ---------------------------------------------------------
        # 여기까지 왔다면 정밀 검색에 실패한 것임.
        # 최후의 수단으로 '가장 비슷한 문장'을 찾아 매칭 시도.

        # 문장 단위로 쪼개서 비교 (속도 최적화)
        # 마침표(.), 물음표(?), 느낌표(!), 줄바꿈(\n) 등을 기준으로 나눔
        candidates = re.split(r'[.?!:\n]+', search_scope_text)

        best_ratio = 0
        best_candidate = ""

        for cand in candidates:
            # 너무 짧은 문장(5글자 미만)은 노이즈일 가능성이 높음
            if len(cand) < 5:
                continue

            # 유사도 계산
            ratio = difflib.SequenceMatcher(None, cand, clean_target).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_candidate = cand

        # 유사도가 60% (0.6) 이상일 때만 찾은 것으로 간주
        if best_ratio >= 0.6:
            # 찾은 문장(best_candidate)이 원문의 어디에 있는지 찾기
            # (split되면서 특수문자가 사라졌을 수 있으므로 find로 다시 위치 추적)
            fuzzy_idx = search_scope_text.find(best_candidate)
            if fuzzy_idx != -1:
                return (start_from + fuzzy_idx), (start_from + fuzzy_idx + len(best_candidate))

        # 모든 방법 실패
        return -1, -1
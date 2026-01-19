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
from langchain_community.tools.tavily_search import TavilySearchResults

# 로컬 DB 레포지토리
from app.service.clio_fact_checker_agent.repo import ManuscriptRepository

class ManuscriptAnalyzer:
    def __init__(self, setting_path: str, character_path: str): # [변경] character_path 추가
        # 1. LLM 설정
        self.llm = ChatUpstage(model="solar-pro")

        # 2. 설정 파일 로드
        # plot.json (기존)
        self.settings = self._load_settings(setting_path)
        # characters.json (신규 추가) -> 여기서 로드합니다.
        self.character_data = self._load_settings(character_path)

        # 3. 허구/설정 키워드 추출 (두 파일 내용을 합쳐서 필터링 목록 생성)
        self.setting_keywords = self._extract_setting_keywords()

        # 4. 리포지토리 및 툴 초기화 (기존 동일)
        self.repo = ManuscriptRepository()
        self.search_tool = TavilySearchResults(k=5, search_depth="advanced")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
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
        """소설 속 허구의 고유명사 + characters.json의 인물들을 필터링 키워드로 추출"""
        keywords = set()

        # 1. plot.json 데이터 처리 (기존 로직 유지)
        plot_data = self.settings
        for char in plot_data.get("characters", []):
            name = char.get("name", "").strip()
            if name: keywords.add(name)

        factions = plot_data.get("world_view", {}).get("factions", [])
        for f in factions:
            if isinstance(f, str):
                keywords.add(f.split("(")[0].strip())

        # 2. [추가] characters.json 데이터 처리
        # 제공해주신 양식은 {"이름": {상세정보}, ...} 형태의 딕셔너리입니다.
        if self.character_data:
            for name_key in self.character_data.keys():
                # "김태평", "이도훈", "더글러스 헤이그" 등의 키값을 추가
                keywords.add(name_key.strip())

        return keywords

    def analyze_manuscript(self, text: str) -> Dict[str, Any]:
        """
        [Rollback] 원자적 명제 분해 없이, 단순 키워드 추출 후 1/2차 검증 수행
        """
        print(f"📄 고증 분석 시작 (총 {len(text)}자)")

        # 1. 텍스트 분할 및 검색 대상(Query) 추출
        chunks = self.text_splitter.split_text(text)
        all_query_items = []

        for chunk in chunks:
            # [수정] 복잡한 명제 분해 없이 심플하게 추출
            items = self._extract_search_queries(chunk)

            for item in items:
                # 위치 찾기 로직 (기존 유지)
                kw = item['keyword']
                origin_snippet = item.get('original_sentence', '')

                start_idx, end_idx = self._find_exact_position(text, origin_snippet, 0)

                # 위치 못 찾으면 재시도 (문장 재추출)
                if start_idx == -1:
                    new_snippet = self._retry_extract_sentence(chunk, kw)
                    if new_snippet:
                        start_idx, end_idx = self._find_exact_position(text, new_snippet, 0)
                        item['original_sentence'] = new_snippet if start_idx != -1 else origin_snippet

                item['start_index'] = start_idx
                item['end_index'] = end_idx
                all_query_items.append(item)

        print(f"   -> 총 {len(all_query_items)}개의 검증 포인트 추출됨")

        known_settings = []
        historical_context = []
        verification_queue = []

        # 2. 검색 수행 (Search)
        for item_data in all_query_items:
            proposition = item_data['keyword']
            query_string = item_data['search_query']
            origin_sent = item_data.get('original_sentence', '')

            # 허구 필터링
            is_fiction = False
            for fiction_term in self.setting_keywords:
                if fiction_term in proposition or fiction_term in origin_sent:
                    is_fiction = True
                    break

            if is_fiction:
                known_settings.append(proposition)
                continue

            print(f"🔍 검색 수행: '{query_string}'")

            # 로컬 DB -> 웹 검색 순서
            search_data = self._check_local_db(query_string)
            if not search_data:
                search_data = self._search_web(query_string)
                time.sleep(0.1)

            if search_data:
                verification_queue.append({
                    "id": len(verification_queue),
                    "keyword": proposition,
                    "query": query_string,
                    "content": search_data['content'],
                    "context": origin_sent,
                    "item_data": item_data,
                    "search_source": search_data.get('source', 'Unknown')
                })

        # 3. 1차/2차 검증 (Verification)
        if verification_queue:
            print(f"🚀 총 {len(verification_queue)}건에 대해 검증을 수행합니다...")

            BATCH_SIZE = 5
            for i in range(0, len(verification_queue), BATCH_SIZE):
                batch_items = verification_queue[i : i + BATCH_SIZE]
                print(f"   -> Batch {i//BATCH_SIZE + 1} 처리 중...")

                # 1차 & 2차 검증 실행
                first_results = self._verify_batch_relevance(batch_items)
                final_results = self._double_check_batch_results(batch_items, first_results)

                # 결과 매핑
                for item in batch_items:
                    item_id = str(item['id'])

                    # 방어 코드: 결과가 dict가 아니면 빈 dict로 처리
                    raw_res_1 = first_results.get(item_id, {})
                    res_1 = raw_res_1 if isinstance(raw_res_1, dict) else {}

                    raw_res_2 = final_results.get(item_id, {})
                    res_2 = raw_res_2 if isinstance(raw_res_2, dict) else {}

                    # 최종 판단: 2차 결과 우선 -> 1차 결과 -> 둘 다 없으면 True(통과)
                    final_is_positive = res_2.get('is_positive', res_1.get('is_positive', True))

                    reason_1 = res_1.get('reason', '판단 불가')
                    reason_2 = res_2.get('reason', '-')
                    combined_reason = f"[1차] {reason_1}\n[2차] {reason_2}"

                    final_obj = {
                        "keyword": item['keyword'],
                        "is_positive": final_is_positive,
                        "reason": combined_reason,
                        "original_sentence": item['context'],
                        "source": item['search_source'],
                        "start_index": item['item_data'].get('start_index'),
                        "end_index": item['item_data'].get('end_index')
                    }

                    historical_context.append(final_obj)

                    if final_is_positive:
                        print(f"      ✅ [통과] {item['keyword']}")
                    else:
                        print(f"      ❌ [오류] {item['keyword']}")

        return {
            "total_checked": len(all_query_items),
            "error_count": len([i for i in historical_context if not i['is_positive']]),
            "historical_context": historical_context,
            "setting_terms_found": list(set(known_settings))
        }

    def _extract_search_queries(self, text: str) -> List[Dict[str, str]]:
        """
        [수정됨] 단순 명사가 아닌 '역사적 사실 관계(명제)'와 '시대적 정합성'을 검증하는 쿼리 생성기
        """
        prompt = """
        당신은 역사 소설의 고증 오류를 찾아내는 '팩트체크 쿼리 설계자'입니다.
        단순한 고유명사 추출이 아니라, **"이 내용이 역사적으로 가능한가?"**를 검증하기 위한 **명제(Proposition)와 맥락**을 추출하세요.

        [추출 기준: 무엇을 검증해야 하는가?]
        1. **행위와 사건의 사실성 (Historical Plausibility):**
           - 실존 인물이 해당 시점에 그 장소에 있었거나, 그 행동을 했는지.
        2. **시대적 불일치 (Anachronism):**
           - 등장한 물건, 용어, 개념이 해당 시대에 존재했는지.
        3. **문화/제도적 배경 (Cultural Context):**
           - 의복, 식사, 의료 행위, 법률 등이 당시 고증에 맞는지.

        [제외 대상 (Negative Rules)]
        - 역사적 맥락이 없는 단순한 일상 묘사 (예: "밥을 먹었다", "잠을 잤다").
        - 수식어가 없는 일반 명사 단독 추출 금지 (예: '병원', '사람', '하늘' -> 절대 금지).
        - **반드시 '검증이 필요한 구체적 서술'이 포함된 경우만 추출.**

        [출력 형식]
        반드시 아래와 같은 **JSON 리스트**만 출력하세요.
        [
            {
                "keyword": "검증 대상 (짧은 구 혹은 주어+서술어 요약)",
                "original_sentence": "본문에서 토씨 하나 안 바꾸고 그대로 복사한 문장 전체",
                "search_query": "구글/위키피디아 검색을 위한 쿼리 (시대 키워드 포함)",
                "reason": "이 항목을 역사적으로 검증해야 하는 구체적인 이유"
            }
        ]
        """

        try:
            # LLM에게 텍스트 전달
            response = self.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"Text: {text[:3500]}") # 문맥 파악을 위해 길이 약간 늘림
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
        """Tavily AI 웹 검색"""
        try:
            # 검색어 보정 (기존 로직 유지)
            if "역사" not in query and "history" not in query.lower():
                final_query = f"{query} 역사 history"
            else:
                final_query = query

            # Tavily 검색 실행 (결과는 리스트 형태로 반환됨)
            # [{'url': '...', 'content': '...'}, ...]
            search_results = self.search_tool.run(final_query)

            if not search_results:
                return None

            # 여러 개의 검색 결과 본문을 하나로 합침
            combined_content = "\n\n".join([
                f"[Source: {res['url']}]\n{res['content']}"
                for res in search_results
            ])

            return {
                "keyword": query,
                "content": combined_content,
                "source": "Web Search (Tavily AI)"
            }
        except Exception as e:
            print(f"⚠️ Tavily 검색 중 오류 발생: {e}")
            return None

    def _verify_batch_relevance(self, batch_items: List[Dict]) -> Dict[str, Dict]:
        """[1차 검증] ID 기반 결과 매핑"""
        items_text = ""
        for item in batch_items:
            items_text += f"""
            ---
            [ID: {item['id']}]
            - 검증 명제: {item['keyword']}
            - 소설 맥락: {item['context']}
            - 검색 결과: {item['content'][:800]}
            """

        prompt = f"""
        역사 팩트체커입니다. 아래 항목들의 사실 여부를 검증하세요.

        [판단 기준]
        - **is_positive**: 명제가 역사적 사실과 부합하면 true, **오류나 시대착오면 false**.
        - **is_relevant**: 검색 자료가 유효하면 true.

        [출력 형식]
        반드시 항목의 **ID(숫자 문자열)**를 키(Key)로 하는 JSON을 반환하세요.
        {{
            "0": {{ "is_relevant": true, "is_positive": false, "reason": "1916년에는 MRE가 없었음" }},
            "1": {{ ... }}
        }}
        """
        try:
            response = self.llm.invoke([SystemMessage(content=prompt)])
            return self._clean_json_string(response.content)
        except Exception: return {}

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

    def _double_check_batch_results(self, batch_items: List[Dict], first_results: Dict) -> Dict:
        """[2차 교차 검증] ID 기반"""
        audit_payload = ""
        for item in batch_items:
            item_id = str(item['id'])
            f_res = first_results.get(item_id, {"is_positive": True, "reason": "Skip"})

            audit_payload += f"""
            ---
            [ID: {item_id}]
            - 명제: {item['keyword']}
            - 증거: {item['content'][:500]}
            - 1차 결론: {"적절" if f_res.get("is_positive") else "오류"} ({f_res.get("reason")})
            """

        prompt = f"""
        최종 감수관입니다. 1차 판정이 타당한지 교차 검증하세요.
        특히 '오류'로 판정된 건이 진짜 오류인지 신중히 확인하세요.

        [출력 형식]
        ID를 키로 하는 JSON 반환:
        {{
            "0": {{ "is_relevant": true, "is_positive": false, "reason": "최종 근거..." }}
        }}
        """
        try:
            response = self.llm.invoke([SystemMessage(content=prompt)])
            return self._clean_json_string(response.content)
        except Exception: return first_results


    def _retry_extract_sentence(self, chunk_text: str, keyword: str) -> str:
        """재시도: 문장 재추출"""
        prompt = f"""
        당신은 텍스트 분석가입니다.
        아래 텍스트에서 키워드 '{keyword}'가 포함된 문장을 **토씨 하나 틀리지 말고 그대로** 추출하세요.
        문장이 너무 길면 해당 부분만 잘라서 출력하고, 없으면 None을 출력하세요.
        """
        try:
            res = self.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"Text: {chunk_text[:2500]}")
            ])
            val = res.content.strip().strip('"\'')
            return None if val == "None" or len(val) < 2 else val
        except: return None

    def _compress_text(self, text: str) -> str:
        """
        [토큰 절약] KoNLPy(Okt)를 사용하여 조사/구두점 제거 후 핵심 품사만 남김
        """
        try:
            from konlpy.tag import Okt
            okt = Okt()

            # 살려둘 품사 (명사, 동사, 형용사, 부사, 숫자, 알파벳)
            # Josa(조사), Punctuation(구두점) 등은 제거됨
            target_pos = ['Noun', 'Verb', 'Adjective', 'Adverb', 'Number', 'Alpha']

            # 형태소 분석 (stem=True: '먹었다' -> '먹다' 원형 복원)
            tokens = okt.pos(text, stem=True)

            filtered_words = []
            for word, pos in tokens:
                if pos in target_pos:
                    filtered_words.append(word)
                # 부정어(Not)는 살려야 고증 오류 방지 가능
                elif word in ["안", "못", "없다", "아니"]:
                    filtered_words.append(word)

            return " ".join(filtered_words)

        except Exception as e:
            print(f"⚠️ 토큰 압축 실패 (KoNLPy 에러): {e}")
            return text # 실패하면 원문 그대로 반환
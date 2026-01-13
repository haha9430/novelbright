import streamlit as st
import time
import uuid
from streamlit_quill import st_quill
import requests
import re
import io
from bs4 import BeautifulSoup

# =========================================================
# 1. 설정 및 CSS (사용자님 디자인 적용)
# =========================================================
st.set_page_config(
    page_title="Moneta Studio",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* 1. 배경색 */
    .stApp { background-color: #FDFBF7; }

    /* 2. 에디터 스타일 (종이 질감) */
    .stQuill {
        background-color: #FFFFFF !important;
        border: 1px solid #EAE4DC !important;
        border-radius: 4px !important;
        padding: 20px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
    }

    /* 3. 모달 및 인풋 */
    div[data-testid="stModal"] textarea { padding: 10px 15px !important; font-family: sans-serif; font-size: 14px; }

    /* 4. 버튼 스타일 */
    div[data-testid="stButton"] button {
        border-radius: 6px !important;
        border: 1px solid #E0D8D0 !important;
        background-color: white !important;
        color: #5D4037 !important;
        transition: all 0.2s;
    }
    div[data-testid="stButton"] button:hover { background-color: #FAF5F0 !important; border-color: #BCAAA4 !important; }

    /* Primary Button */
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #8D6E63 !important;
        color: white !important;
        border: none !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover { background-color: #6D4C41 !important; }

    /* 5. 사이드바 */
    section[data-testid="stSidebar"] { background-color: #F9F8F6 !important; }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        background-color: transparent !important;
        border: none !important;
        text-align: left !important;
        padding-left: 8px !important;
        box-shadow: none !important;
        color: #555555 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
        background-color: #EBEBEB !important;
        color: #000000 !important;
        font-weight: 500 !important;
    }

    /* 6. 타이틀 인풋 */
    .doc-title-input input {
        font-family: 'KoPub Batang', serif;
        font-size: 34px !important;
        font-weight: 700 !important;
        color: #333 !important;
        background-color: transparent !important;
        border: none !important;
        padding: 0px !important;
    }
    .doc-title-input input:focus { box-shadow: none !important; }

    /* 7. 플롯/자료실 카드 */
    .ghost-input input { background: transparent !important; border: none !important; font-weight: bold; color: #333; }
    .ghost-input input:focus { background: #f9f9f9 !important; border-bottom: 2px solid #FF6B6B !important; }

    .moneta-card { padding: 15px; border-radius: 8px; background: white; border: 1px solid #eee; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }

    /* 플롯 가로 스크롤 (컨테이너 격리) */
    div[data-testid="stVerticalBlockBorderWrapper"] { border: none !important; padding: 0px !important; overflow-x: auto !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] { width: max-content !important; min-width: 100%; }
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="column"] { width: 300px !important; min-width: 300px !important; flex: 0 0 300px !important; margin-right: 12px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. 상태 초기화
# =========================================================
if "page" not in st.session_state: st.session_state.page = "home"
if "show_moneta" not in st.session_state: st.session_state.show_moneta = False
if "current_project_id" not in st.session_state: st.session_state.current_project_id = None
if "analysis_results" not in st.session_state: st.session_state.analysis_results = {}
if "current_doc_id" not in st.session_state: st.session_state.current_doc_id = None

# 플롯 상태
if "active_plot_idx" not in st.session_state: st.session_state.active_plot_idx = 0
if "selected_block_id" not in st.session_state: st.session_state.selected_block_id = None
if "is_adding_part" not in st.session_state: st.session_state.is_adding_part = False

# 자료실 상태
if "selected_material_id" not in st.session_state: st.session_state.selected_material_id = None

# 더미 데이터
if "projects" not in st.session_state:
    st.session_state.projects = [
        {
            "id": str(uuid.uuid4()),
            "title": "지옥같은 전쟁에 떨어졌다.",
            "tags": ["판타지", "전쟁"],
            "desc": "눈을 떠보니 참호 속이었다...",
            "last_edited": "방금 전",
            "characters": [],
            "materials": [],
            "documents": [{"id": "doc1", "title": "프롤로그", "content": "<p>눈을 떠보니...</p>"}],
            "plots": [{"id": "def", "name": "메인 플롯", "desc": "기본 플롯", "parts": []}]
        }
    ]


# =========================================================
# 3. Helper Functions
# =========================================================
def get_current_project():
    if st.session_state.current_project_id is None and st.session_state.projects:
        st.session_state.current_project_id = st.session_state.projects[0]['id']
    return next((p for p in st.session_state.projects if p['id'] == st.session_state.current_project_id), None)


def get_current_document(proj):
    if not proj.get('documents'):
        new_doc = {"id": str(uuid.uuid4()), "title": "새 문서", "content": ""}
        proj['documents'] = [new_doc]
        st.session_state.current_doc_id = new_doc['id']
        return new_doc

    if st.session_state.current_doc_id is None:
        doc = proj['documents'][0]
        st.session_state.current_doc_id = doc['id']
        return doc

    doc = next((d for d in proj['documents'] if d['id'] == st.session_state.current_doc_id), None)
    if not doc:
        doc = proj['documents'][0]
        st.session_state.current_doc_id = doc['id']
    return doc


# =========================================================
# 4. Modals (Dialogs)
# =========================================================
@st.dialog("🔍 통합 검색", width="large")
def search_modal(project):
    st.markdown("### 무엇을 찾고 계신가요?")
    query = st.text_input("검색어", placeholder="문서, 자료, 인물 검색...", label_visibility="collapsed")
    if query:
        st.divider()
        found = False
        # 문서 검색
        for doc in project.get('documents', []):
            clean_content = re.sub('<[^<]+?>', '', doc.get('content', ''))
            if query in doc['title'] or query in clean_content:
                found = True
                with st.container(border=True):
                    st.markdown(f"**📄 {doc['title']}**")
                    st.caption(clean_content[:100] + "...")
        # 자료실 검색
        for mat in project.get('materials', []):
            if query in mat['title'] or query in mat['content']:
                found = True
                icon = "🏛️" if mat['category'] == "역사" else "⚙️"
                with st.container(border=True):
                    st.markdown(f"**{icon} {mat['title']}** <small>({mat['category']})</small>", unsafe_allow_html=True)
                    st.caption(mat['content'][:100] + "...")
        if not found: st.info("검색 결과가 없습니다.")


@st.dialog("새 작품 만들기")
def create_project_modal():
    title = st.text_input("제목")
    if st.button("생성"):
        st.session_state.projects.append({
            "id": str(uuid.uuid4()), "title": title, "tags": [], "desc": "", "last_edited": "방금",
            "characters": [], "materials": [], "plots": [], "documents": []
        })
        st.rerun()


@st.dialog("문서 이름 변경")
def rename_document_modal(doc):
    new_t = st.text_input("새 이름", value=doc['title'])
    if st.button("변경"): doc['title'] = new_t; st.rerun()


@st.dialog("새 인물 추가")
def add_character_modal(project):
    name = st.text_input("이름")
    desc = st.text_area("설명")
    if st.button("추가"):
        project['characters'].append({"id": str(uuid.uuid4()), "name": name, "tag": "", "desc": desc})
        st.rerun()


# =========================================================
# 5. Renderers
# =========================================================
def render_sidebar(current_proj):
    with st.sidebar:
        if st.button("🏠 홈으로", use_container_width=True): st.session_state.page = "home"; st.rerun()
        st.markdown(f"## {current_proj['title']}")
        if st.button("🔍 검색하기", use_container_width=True): search_modal(current_proj)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        if st.button("👤  등장인물", use_container_width=True): st.session_state.page = "characters"; st.rerun()
        if st.button("📅  플롯", use_container_width=True): st.session_state.page = "plot"; st.rerun()
        # [NEW] 자료실 버튼 추가
        if st.button("📚  자료실", use_container_width=True): st.session_state.page = "materials"; st.rerun()

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns([8, 2])
        c1.caption("문서")
        if c2.button("➕", key="add_doc"):
            new_doc = {"id": str(uuid.uuid4()), "title": "새 문서", "content": ""}
            current_proj['documents'].append(new_doc)
            st.session_state.current_doc_id = new_doc['id']
            st.session_state.page = "editor"
            st.rerun()
        if "documents" not in current_proj: current_proj['documents'] = []
        for doc in current_proj['documents']:
            is_active = (doc['id'] == st.session_state.current_doc_id) and (st.session_state.page == "editor")
            btn_type = "primary" if is_active else "secondary"
            c_doc, c_opt = st.columns([8.5, 1.5], gap="small")
            with c_doc:
                if st.button(f"📄 {doc['title']}", key=f"d_{doc['id']}", type=btn_type, use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.session_state.page = "editor"
                    st.rerun()
            with c_opt:
                with st.popover("⋮"):
                    if st.button("이름 변경", key=f"ren_{doc['id']}"): rename_document_modal(doc)
                    if st.button("삭제", key=f"del_{doc['id']}"):
                        current_proj['documents'].remove(doc)
                        if st.session_state.current_doc_id == doc['id']: st.session_state.current_doc_id = None
                        st.rerun()


def render_home():
    st.title("내 작품")
    if st.button("➕ 새 작품"): create_project_modal()
    st.divider()
    cols = st.columns(3)
    for i, p in enumerate(st.session_state.projects):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(p['title'])
                st.caption(p['desc'])
                if st.button("작업하기", key=f"go_{p['id']}", use_container_width=True):
                    st.session_state.current_project_id = p['id']
                    st.session_state.page = "editor"
                    st.rerun()


def render_editor():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()
    current_doc = get_current_document(proj)
    quill_key = f"quill_{current_doc['id']}"

    render_sidebar(proj)

    # ---------------------------------------------------------
    # [Logic] 글자 수 계산 & 콘텐츠 안전하게 가져오기
    # ---------------------------------------------------------
    # 1. 세션 스테이트에서 가져오되, None이면 빈 문자열("")로 변환
    content_raw = st.session_state.get(quill_key)
    if content_raw is None:
        content_source = current_doc.get('content', "")
    else:
        content_source = content_raw

    # 2. 글자 수 계산
    char_count_total = 0
    char_count_no_space = 0

    if content_source:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content_source, "html.parser")
        plain_text = soup.get_text()
        char_count_total = len(plain_text)
        char_count_no_space = len(plain_text.replace(" ", "").replace("\n", ""))

    # ---------------------------------------------------------
    # [UI] 헤더 영역 (제목 | 통계 | 버튼)
    # ---------------------------------------------------------
    c_title, c_stats, c_btn = st.columns([6, 2.5, 1.5], gap="small", vertical_alignment="bottom")

    with c_title:
        st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)
        new_t = st.text_input("t", value=current_doc['title'], key=f"t_{current_doc['id']}",
                              label_visibility="collapsed", placeholder="제목 없음")
        if new_t != current_doc['title']:
            current_doc['title'] = new_t
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # 글자 수 통계
    with c_stats:
        st.markdown(
            f"""
            <div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
                <span style="font-weight:bold; color:#5D4037;">{char_count_total:,}</span> 자 
                <span style="font-size:11px; color:#aaa;">(공백제외 {char_count_no_space:,})</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c_btn:
        lbl = "✖ 닫기" if st.session_state.show_moneta else "✨ Moneta"
        if st.button(lbl, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.show_moneta
            st.rerun()

    # ---------------------------------------------------------
    # [UI] Moneta 패널 (맞춤법 제거됨)
    # ---------------------------------------------------------
    if st.session_state.show_moneta:
        with st.container(border=True):
            c_info, c_btn = st.columns([7, 3])
            with c_info:
                st.caption("역사적 고증과 설정 충돌을 분석합니다.")
            with c_btn:
                if st.button("🚀 전체 스캔", use_container_width=True, type="primary"):
                    st.session_state.analysis_results[current_doc['id']] = []
                    with st.spinner("분석 중..."):
                        try:
                            content_source_txt = io.BytesIO(content_source.encode("utf-8"))
                            content_source_txt.name = f"{current_doc['title']}.txt"  # 파일명 지정 필요
                            form_data_analyzer = {"file": (content_source_txt.name, content_source_txt, "text/plain")}

                            # 안전하게 처리된 content_source 전송
                            res = requests.post("http://127.0.0.1:8000/manuscript/analyze", files=form_data_analyzer, data={"title": current_doc['title']})
                            print(res)
                            if res.status_code == 200:
                                st.session_state.analysis_results[current_doc['id']] = res.json()
                                st.rerun()
                            else:
                                st.error(f"오류: {res.text}")
                        except Exception as e:
                            st.error(f"연결 실패: {e}")

            # 분석 결과 표시
            result_data = st.session_state.analysis_results.get(current_doc['id'], {})

            # 데이터가 비어있지 않고, 우리가 기대하는 구조(dict)인지 확인
            if result_data and isinstance(result_data, dict):

                # 1. 요약 정보 표시
                analysis = result_data.get("analysis_result", {})
                found_count = analysis.get("found_entities_count", 0)

                st.divider()
                st.subheader(f"📊 분석 결과 리포트 ({found_count}건 감지)")

                # 2. 역사적 검증 (Historical Context) 리스트 순회
                history_items = analysis.get("historical_context", [])

                if not history_items:
                    st.info("검출된 역사적 특이사항이 없습니다.")

                for item in history_items:
                    # 1. 데이터 준비
                    is_positive = item.get("is_positive", False)
                    keyword = item.get('keyword', '키워드 없음')
                    original_sentence = item.get('original_sentence', '')
                    reason = item.get('reason', '')

                    # 2. 카드 컨테이너 생성 (외곽선 있는 박스)
                    with st.container(border=True):

                        # [헤더 영역] 상태 아이콘과 키워드 배치
                        col_header_L, col_header_R = st.columns([0.65, 0.35])

                        with col_header_L:
                            if is_positive:
                                st.markdown("### ✅ 고증 일치")
                            else:
                                st.markdown("### ⚠️ 고증 오류 의심")

                        with col_header_R:
                            # 키워드를 코드 블록 스타일로 보여주어 뱃지처럼 연출
                            st.markdown(f"**KEYWORD**")
                            st.code(keyword, language="text")

                        # [원문 영역] 인용구 스타일 활용
                        st.caption("❝ 원문 발췌")
                        st.markdown(f"> *{original_sentence}*")

                        st.divider() # 구분선

                        # [분석 결과 영역] 색상 박스로 강조
                        # 일치하면 초록색 박스(success), 오류면 빨간색 박스(error) 사용
                        if is_positive:
                            st.success(f"**🕵️ 분석 결과**\n\n{reason}", icon="✅")
                        else:
                            st.error(f"**🕵️ 분석 결과**\n\n{reason}", icon="⚠️")

        if isinstance(result_data, list):
            for m in result_data:
                if isinstance(m, dict):
                    bg = "#FFF5F5" if m.get('role') == "story" else "#F0F8FF"
                    border = "#D32F2F" if m.get('role') == "story" else "#0277BD"
                    st.markdown(
                        f"""<div class="moneta-card" style="background:{bg}; border-left:4px solid {border}"><b>{m.get('msg', '')}</b><br><span style="font-size:13px; color:#555">💡 제안: {m.get('fix', '')}</span></div>""",
                        unsafe_allow_html=True)

    # ---------------------------------------------------------
    # [UI] 에디터 및 저장
    # ---------------------------------------------------------
    content = st_quill(value=current_doc.get('content', ""), key=quill_key)
    if content != current_doc.get('content', ""):
        current_doc['content'] = content

    with st.sidebar:
        st.divider()
        if st.button("💾 원고 저장하기", type="primary", use_container_width=True):
            with st.spinner("저장 중..."):
                try:
                    payload = {"doc_id": current_doc['id'], "title": current_doc['title'], "content": content}
                    requests.post("http://127.0.0.1:8000/documents/save", json=payload)
                    st.toast("저장 완료!", icon="✅")
                except Exception as e:
                    st.error(f"저장 실패: {e}")

def render_materials():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()
    if "materials" not in proj: proj['materials'] = []

    render_sidebar(proj)
    st.title("📚 자료실")
    st.divider()

    c_list, c_edit = st.columns([1, 2], gap="large")

    # 목록
    with c_list:
        c1, c2 = st.columns([2, 1])
        c1.subheader("목록")
        if c2.button("＋ 추가", use_container_width=True):
            new_mat = {"id": str(uuid.uuid4()), "title": "새 자료", "category": "설정", "content": ""}
            proj['materials'].insert(0, new_mat)
            st.session_state.selected_material_id = new_mat['id']
            st.rerun()

        for mat in proj['materials']:
            is_sel = (mat['id'] == st.session_state.selected_material_id)
            icon = "🏛️" if mat['category'] == "역사" else "⚙️"
            if st.button(f"{icon} {mat['title']}", key=f"m_{mat['id']}", use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state.selected_material_id = mat['id']
                st.rerun()

    # 상세 편집
    with c_edit:
        sel_mat = next((m for m in proj['materials'] if m['id'] == st.session_state.selected_material_id), None)
        if sel_mat:
            with st.container(border=True):
                c1, c2 = st.columns([8, 1])
                c1.caption("자료 상세 편집")
                if c2.button("🗑", key=f"del_m_{sel_mat['id']}"):
                    try:
                        requests.delete(f"http://127.0.0.1:8000/materials/{sel_mat['id']}")
                        proj['materials'].remove(sel_mat)
                        st.session_state.selected_material_id = None
                        st.toast("삭제됨")
                        st.rerun()
                    except:
                        st.error("삭제 실패 (서버 연결 확인)")

                new_t = st.text_input("제목", value=sel_mat['title'])
                if new_t != sel_mat['title']: sel_mat['title'] = new_t

                new_c = st.selectbox("분류", ["역사", "설정", "인물", "기타"],
                                     index=["역사", "설정", "인물", "기타"].index(sel_mat['category']) if sel_mat[
                                                                                                      'category'] in [
                                                                                                      "역사", "설정", "인물",
                                                                                                      "기타"] else 3)
                if new_c != sel_mat['category']: sel_mat['category'] = new_c

                new_ctx = st.text_area("내용", value=sel_mat['content'], height=300)
                if new_ctx != sel_mat['content']: sel_mat['content'] = new_ctx

                st.divider()
                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    try:
                        requests.post("http://127.0.0.1:8000/materials/save", json=sel_mat)
                        st.toast("저장 완료!", icon="✅")
                    except:
                        st.error("저장 실패 (서버 연결 확인)")
        else:
            st.info("자료를 선택하거나 추가하세요.")


def render_plot():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()

    if "plots" not in proj: proj["plots"] = [{"id": "def", "name": "메인 플롯", "desc": "", "parts": []}]
    if st.session_state.active_plot_idx >= len(proj['plots']): st.session_state.active_plot_idx = 0
    if "selected_block_id" not in st.session_state: st.session_state.selected_block_id = None

    # 가로 스크롤 CSS
    st.markdown("""<style>div[data-testid="stVerticalBlockBorderWrapper"] { overflow-x: auto !important; }</style>""",
                unsafe_allow_html=True)

    render_sidebar(proj)

    # 탭
    plots = proj['plots']
    with st.container():
        cols = st.columns(len(plots) + 1)
        for i, p in enumerate(plots):
            with cols[i]:
                if st.button(p['name'], key=f"pt_{p['id']}",
                             type="primary" if i == st.session_state.active_plot_idx else "secondary",
                             use_container_width=True):
                    st.session_state.active_plot_idx = i;
                    st.rerun()
        with cols[-1]:
            if st.button("＋", key="add_pl"):
                proj['plots'].append({"id": str(uuid.uuid4()), "name": "새 플롯", "parts": []})
                st.session_state.active_plot_idx = len(proj['plots']) - 1;
                st.rerun()

    st.divider()
    curr_plot = plots[st.session_state.active_plot_idx]

    # 플롯 정보
    c1, c2 = st.columns([8, 1])
    with c1:
        new_pn = st.text_input("플롯 이름", value=curr_plot['name'], key=f"pnn_{curr_plot['id']}",
                               label_visibility="collapsed")
        if new_pn != curr_plot['name']: curr_plot['name'] = new_pn
    with c2:
        if len(plots) > 1 and st.button("🗑", key="del_pl"):
            proj['plots'].pop(st.session_state.active_plot_idx)
            st.session_state.active_plot_idx = 0;
            st.rerun()

    st.markdown("###### 📜 전체 줄거리")
    story_k = f"s_{curr_plot['id']}"
    if 'story' not in curr_plot: curr_plot['story'] = ""
    new_s = st.text_area("줄거리", value=curr_plot['story'], key=story_k, height=100, label_visibility="collapsed")
    if new_s != curr_plot['story']: curr_plot['story'] = new_s

    st.markdown("<br>", unsafe_allow_html=True)

    selected_block = None
    parent_part = None
    if st.session_state.selected_block_id:
        for part in curr_plot['parts']:
            for block in part['blocks']:
                if block['id'] == st.session_state.selected_block_id:
                    selected_block = block
                    parent_part = part
                    break
            if selected_block: break

    # 레이아웃 분할
    if selected_block:
        main_cols = st.columns([7, 3])
        col_board_area = main_cols[0]
        col_inspector = main_cols[1]
    else:
        col_board_area = st.container()

    # 보드
    with col_board_area:
        with st.container(border=True):
            cols = st.columns(len(curr_plot['parts']) + 1)
            for i, part in enumerate(curr_plot['parts']):
                with cols[i]:
                    with st.container(border=True):
                        h1, h2 = st.columns([4, 1])
                        with h1:
                            st.markdown('<div class="ghost-input">', unsafe_allow_html=True)
                            np = st.text_input(f"pn_{part['id']}", value=part['name'], label_visibility="collapsed")
                            if np != part['name']: part['name'] = np
                            st.markdown('</div>', unsafe_allow_html=True)
                        with h2:
                            with st.popover("⋮"):
                                if st.button("⬅️", key=f"l_{part['id']}"):
                                    if i > 0:
                                        curr_plot['parts'][i], curr_plot['parts'][i - 1] = curr_plot['parts'][i - 1], \
                                        curr_plot['parts'][i]
                                        st.rerun()
                                if st.button("➡️", key=f"r_{part['id']}"):
                                    if i < len(curr_plot['parts']) - 1:
                                        curr_plot['parts'][i], curr_plot['parts'][i + 1] = curr_plot['parts'][i + 1], \
                                        curr_plot['parts'][i]
                                        st.rerun()
                                if st.button("🗑", key=f"dp_{part['id']}"):
                                    curr_plot['parts'].remove(part);
                                    st.rerun()
                        st.markdown("---")
                        for block in part['blocks']:
                            txt = block['content'] if block['content'] else "내용 없음"
                            is_sel = (block['id'] == st.session_state.selected_block_id)
                            if st.button(txt[:20] + ("..." if len(txt) > 20 else ""), key=f"b_{block['id']}",
                                         type="primary" if is_sel else "secondary", use_container_width=True):
                                st.session_state.selected_block_id = block['id']
                                st.rerun()
                        if st.button("＋ 블록", key=f"ab_{part['id']}"):
                            part['blocks'].append({"id": str(uuid.uuid4()), "content": ""})
                            st.rerun()

            with cols[-1]:
                if not st.session_state.is_adding_part:
                    if st.button("＋ 파트 추가"): st.session_state.is_adding_part = True; st.rerun()
                else:
                    with st.container(border=True):
                        np_val = st.text_input("새 파트명")
                        c1, c2 = st.columns(2)
                        if c1.button("취소"): st.session_state.is_adding_part = False; st.rerun()
                        if c2.button("추가"):
                            curr_plot['parts'].append(
                                {"id": str(uuid.uuid4()), "name": np_val if np_val else "새 파트", "blocks": []})
                            st.session_state.is_adding_part = False;
                            st.rerun()

    # 인스펙터
    if selected_block and 'col_inspector' in locals():
        with col_inspector:
            with st.container(border=True):
                h1, h2 = st.columns([1, 8])
                with h1:
                    if st.button("✕", key="close_insp"):
                        st.session_state.selected_block_id = None
                        st.rerun()
                with h2:
                    st.markdown(
                        f'<div style="color:#888; font-size:13px; margin-top:5px">↳ <b>{parent_part["name"]}</b></div>',
                        unsafe_allow_html=True)

                with st.expander("옵션"):
                    if st.button("복제", use_container_width=True):
                        new_bk = selected_block.copy()
                        new_bk['id'] = str(uuid.uuid4())
                        parent_part['blocks'].insert(parent_part['blocks'].index(selected_block) + 1, new_bk)
                        st.rerun()
                    if st.button("삭제", type="primary", use_container_width=True):
                        parent_part['blocks'].remove(selected_block)
                        st.session_state.selected_block_id = None
                        st.rerun()

                st.markdown("#### 블록 편집")
                new_content = st.text_area("내용", value=selected_block.get('content', ''), height=200,
                                           key=f"ed_c_{selected_block['id']}")
                if new_content != selected_block.get('content', ''):
                    selected_block['content'] = new_content

                st.caption("등장인물")
                char_opts = [c['name'] for c in proj.get('characters', [])]
                current_chars = [c for c in selected_block.get('characters', []) if c in char_opts]
                new_chars = st.multiselect("인물 선택", options=char_opts, default=current_chars,
                                           key=f"ed_ch_{selected_block['id']}")
                if new_chars != current_chars: selected_block['characters'] = new_chars

                st.caption("관련 문서")
                doc_opts = [d['title'] for d in proj.get('documents', [])]
                current_docs = [d for d in selected_block.get('docs', []) if d in doc_opts]
                new_docs = st.multiselect("문서 선택", options=doc_opts, default=current_docs,
                                          key=f"ed_doc_{selected_block['id']}")
                if new_docs != current_docs: selected_block['docs'] = new_docs


def render_characters():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()
    render_sidebar(proj)
    st.title("등장인물")
    if st.button("＋ 인물 추가"): add_character_modal(proj)
    st.divider()
    for char in proj['characters']:
        with st.container(border=True):
            st.subheader(char['name'])
            st.caption(char['tag'])
            st.write(char['desc'])
            if st.button("삭제", key=f"dc_{char['id']}"):
                proj['characters'].remove(char);
                st.rerun()


# =========================================================
# 6. Main Routing
# =========================================================
if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "editor":
    render_editor()
elif st.session_state.page == "characters":
    render_characters()
elif st.session_state.page == "plot":
    render_plot()
elif st.session_state.page == "materials":
    render_materials()
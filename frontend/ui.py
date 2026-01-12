import streamlit as st
import time
import uuid

# =========================================================
# 1. 설정 및 CSS
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
    .stTextArea textarea[aria-label="본문"] {
        background-color: #FFFFFF !important;
        border: 1px solid #EAE4DC !important;
        padding: 60px 80px !important;
        font-family: 'KoPub Batang', serif !important;
        line-height: 2.1 !important;
        font-size: 17px !important;
        color: #333333 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
        height: 800px !important;
    }

    /* 3. 모달 입력창 초기화 */
    div[data-testid="stModal"] textarea {
        padding: 10px 15px !important;
        font-family: sans-serif !important;
        font-size: 14px !important;
    }

    /* 4. 버튼 스타일 */
    div[data-testid="stButton"] button {
        border-radius: 6px !important;
        border: 1px solid #E0D8D0 !important;
        background-color: white !important;
        color: #5D4037 !important;
        transition: all 0.2s;
    }
    div[data-testid="stButton"] button:hover {
        background-color: #FAF5F0 !important;
        border-color: #BCAAA4 !important;
    }

    /* Primary */
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #8D6E63 !important;
        color: white !important;
        border: none !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #6D4C41 !important;
    }

    /* 5. 사이드바 스타일 */
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
    section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
        background-color: #E0E0E0 !important;
        color: #000000 !important;
        font-weight: bold !important;
        border-radius: 6px !important;
    }

    /* 6. 인라인 에디트 스타일 */
    .doc-title-input input {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 34px !important;
        font-weight: 700 !important;
        color: #333333 !important;
        background-color: transparent !important;
        border: none !important;
        padding: 0px !important;
        margin-bottom: 10px !important;
    }
    .doc-title-input input:focus { box-shadow: none !important; }

    .part-title-input input { font-weight: bold !important; font-size: 16px !important; background-color: transparent !important; border: none !important; }
    .part-desc-input input { font-size: 13px !important; color: #888888 !important; background-color: transparent !important; border: none !important; }
    .new-block-input input { background-color: transparent !important; border: none !important; font-size: 14px !important; }

    /* 7. 카드 및 컨테이너 */
    .block-card-container { background-color: #FFFFFF; border: 1px solid #EAEAEA; border-radius: 6px; padding: 10px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
    .moneta-card { padding: 18px; border-radius: 8px; background-color: #FFFFFF; border: 1px solid #F0EAE6; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 12px; }

    header {visibility: hidden;}
    .block-container { padding-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. 상태 관리
# =========================================================
if "page" not in st.session_state: st.session_state.page = "home"
if "show_moneta" not in st.session_state: st.session_state.show_moneta = False
if "current_project_id" not in st.session_state: st.session_state.current_project_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "active_plot_idx" not in st.session_state: st.session_state.active_plot_idx = 0
if "current_doc_id" not in st.session_state: st.session_state.current_doc_id = None

# 프로젝트 데이터
if "projects" not in st.session_state:
    st.session_state.projects = [
        {
            "id": str(uuid.uuid4()),
            "title": "지옥같은 전쟁에 떨어졌다.",
            "tags": ["판타지", "전쟁"],
            "desc": "눈을 떠보니 참호 속이었다...",
            "last_edited": "방금 전",
            "characters": [
                {"id": "c1", "name": "이성훈", "tag": "주인공, 헌터", "desc": "32세, 고인물 유저"},
                {"id": "c2", "name": "서아라", "tag": "히로인, 힐러", "desc": "성훈의 파트너"}
            ],
            "documents": [
                {"id": "doc1", "title": "프롤로그", "content": "눈을 떠보니 낯선 천장이었다...\n\n어디선가 매캐한 화약 냄새가 났다."},
                {"id": "doc2", "title": "1화: 참호 속으로", "content": "포탄 소리가 귓가를 때렸다.\n\n콰아앙!"}
            ],
            "plots": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "메인 플롯",
                    "desc": "전체적인 이야기 흐름",
                    "parts": [
                        {"id": "p1", "name": "파트 1", "desc": "기", "blocks": [{"id": "b1", "content": "주인공이 눈을 뜬다."}]},
                        {"id": "p2", "name": "파트 2", "desc": "승", "blocks": [{"id": "b2", "content": "몬스터의 습격."}]},
                    ]
                }
            ]
        }
    ]


# =========================================================
# 3. 헬퍼 함수 & 모달
# =========================================================
def get_current_project():
    return next((p for p in st.session_state.projects if p['id'] == st.session_state.current_project_id), None)


def get_current_document(proj):
    if not proj.get('documents'):
        new_doc = {"id": str(uuid.uuid4()), "title": "새 문서", "content": ""}
        proj['documents'] = [new_doc]
        st.session_state.current_doc_id = new_doc['id']
        return new_doc
    doc = next((d for d in proj['documents'] if d['id'] == st.session_state.current_doc_id), None)
    if not doc:
        doc = proj['documents'][0]
        st.session_state.current_doc_id = doc['id']
    return doc


@st.dialog("새 작품 만들기")
def create_project_modal():
    st.markdown("### 새로운 세계를 창조해 보세요.")
    title = st.text_input("제목", placeholder="예: 전지적 독자 시점")
    desc = st.text_input("한 줄 소개", placeholder="작품의 핵심 컨셉")
    tags = st.text_input("태그", placeholder="#판타지 #회귀")
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    if c1.button("취소", use_container_width=True): st.rerun()
    if c2.button("생성하기", type="primary", use_container_width=True):
        if title:
            default_plots = [{"id": str(uuid.uuid4()), "name": "메인 플롯", "desc": "메인 스토리", "parts": []}]
            default_docs = [{"id": str(uuid.uuid4()), "title": "프롤로그", "content": ""}]
            st.session_state.projects.append({
                "id": str(uuid.uuid4()), "title": title, "desc": desc, "tags": tags.split(","),
                "last_edited": "방금", "characters": [], "plots": default_plots, "documents": default_docs
            })
            st.rerun()


@st.dialog("문서 이름 변경")
def rename_document_modal(doc):
    new_title = st.text_input("문서 제목", value=doc['title'])
    if st.button("변경 저장", type="primary", use_container_width=True):
        doc['title'] = new_title
        st.rerun()


@st.dialog("새 인물 추가")
def add_character_modal(project):
    name = st.text_input("이름", placeholder="예: 홍길동")
    tag = st.text_input("태그/역할", placeholder="예: 주인공, 빌런")
    desc = st.text_area("설명", placeholder="성격이나 특징을 입력하세요")
    if st.button("추가하기", type="primary", use_container_width=True):
        if name:
            project['characters'].append({"id": str(uuid.uuid4()), "name": name, "tag": tag, "desc": desc})
            st.rerun()


@st.dialog("인물 정보 수정")
def edit_character_modal(project, char_id):
    char = next((c for c in project['characters'] if c['id'] == char_id), None)
    if not char: st.rerun()
    new_name = st.text_input("이름", value=char['name'])
    new_tag = st.text_input("태그/역할", value=char['tag'])
    new_desc = st.text_area("설명", value=char['desc'])
    col1, col2 = st.columns(2)
    if col1.button("수정 완료", type="primary", use_container_width=True):
        char['name'] = new_name
        char['tag'] = new_tag
        char['desc'] = new_desc
        st.rerun()
    if col2.button("삭제", use_container_width=True):
        project['characters'].remove(char)
        st.rerun()


# =========================================================
# 5. 화면 렌더링
# =========================================================

def render_sidebar(current_proj):
    with st.sidebar:
        if st.button("🏠 홈으로", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        st.markdown(f"## {current_proj['title']}")
        st.text_input("검색", placeholder="검색...", label_visibility="collapsed")
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        if st.button("👤  등장인물", use_container_width=True):
            st.session_state.page = "characters"
            st.rerun()
        if st.button("📅  플롯", use_container_width=True):
            st.session_state.page = "plot"
            st.rerun()

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        c_head, c_plus = st.columns([8, 2])
        c_head.caption("문서")
        if c_plus.button("➕", key="add_doc_btn"):
            new_doc = {"id": str(uuid.uuid4()), "title": "새 문서", "content": ""}
            current_proj['documents'].append(new_doc)
            st.session_state.current_doc_id = new_doc['id']
            st.session_state.page = "editor"
            st.rerun()

        if "documents" not in current_proj: current_proj['documents'] = []
        for doc in current_proj['documents']:
            is_active = (doc['id'] == st.session_state.current_doc_id) and (st.session_state.page == "editor")
            btn_type = "primary" if is_active else "secondary"
            icon = "📄"
            c_doc, c_menu = st.columns([0.85, 0.15], gap="small", vertical_alignment="center")
            with c_doc:
                if st.button(f"{icon} {doc['title']}", key=f"nav_{doc['id']}", type=btn_type, use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.session_state.page = "editor"
                    st.rerun()
            with c_menu:
                with st.popover("⋮", use_container_width=True):
                    if st.button("✏️ 이름 변경", key=f"ren_d_{doc['id']}", use_container_width=True):
                        rename_document_modal(doc)
                    if st.button("📄 복제", key=f"dup_d_{doc['id']}", use_container_width=True):
                        new_doc = doc.copy()
                        new_doc['id'] = str(uuid.uuid4())
                        new_doc['title'] += " (복사본)"
                        current_proj['documents'].append(new_doc)
                        st.rerun()
                    if st.button("🗑 삭제", key=f"del_d_{doc['id']}", type="primary", use_container_width=True):
                        current_proj['documents'].remove(doc)
                        if st.session_state.current_doc_id == doc['id']:
                            st.session_state.current_doc_id = None
                        st.rerun()


def render_home():
    c1, c2 = st.columns([8, 2])
    with c1:
        st.title("내 작품")
    with c2:
        if st.button("➕ 새 작품", type="primary", use_container_width=True): create_project_modal()
    st.markdown("---")
    if not st.session_state.projects:
        st.info("작품이 없습니다.")
        return
    cols = st.columns(3)
    for i, p in enumerate(st.session_state.projects):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(p["title"])
                st.caption(" ".join([f"#{t}" for t in p["tags"]]) if p["tags"] else "#태그없음")
                st.text(p["desc"][:40] + "...")
                st.markdown(f"<small style='color:#8D6E63'>수정: {p['last_edited']}</small>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                b1, b2 = st.columns([3, 1])
                if b1.button("작업하기", key=f"open_{p['id']}", use_container_width=True):
                    st.session_state.current_project_id = p['id']
                    st.session_state.page = "editor"
                    st.rerun()
                if b2.button("🗑", key=f"del_{p['id']}", use_container_width=True):
                    st.session_state.projects.remove(p)
                    st.rerun()


def render_editor():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()
    current_doc = get_current_document(proj)
    render_sidebar(proj)

    # 1. 헤더 (제목 + Moneta 버튼)
    # 글자수 통계 컬럼 삭제, 비율 조정 [8, 2]
    c_title, c_moneta = st.columns([8, 2], gap="small")

    with c_title:
        # 노션 스타일 제목 수정
        st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)
        new_title = st.text_input("doc_title", value=current_doc['title'], key=f"title_{current_doc['id']}",
                                  label_visibility="collapsed", placeholder="제목 없음")
        if new_title != current_doc['title']:
            current_doc['title'] = new_title
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c_moneta:
        btn_label = "✖ 닫기" if st.session_state.show_moneta else "✨ Moneta"
        btn_type = "secondary" if st.session_state.show_moneta else "primary"
        if st.button(btn_label, type=btn_type, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.show_moneta
            st.rerun()

    # Moneta 패널
    if st.session_state.show_moneta:
        with st.container(border=True):
            c_desc, c_act = st.columns([7, 3], gap="medium")
            with c_desc:
                st.markdown("**🤖 Moneta AI 분석 센터**")
                st.caption("역사 고증(Clio)과 설정 오류(Story Keeper)를 통합 검토합니다.")
            with c_act:
                if st.button("🚀 전체 스캔 시작", type="primary", use_container_width=True):
                    with st.spinner("모네타가 문서를 읽는 중..."):
                        time.sleep(1.0)
                        st.session_state.messages = [
                            {"role": "clio", "msg": "나폴레옹 사망은 1821년입니다.", "fix": "1821년으로 수정"},
                            {"role": "story", "msg": "심연의 군주는 소멸했습니다.", "fix": "잔재로 변경"}
                        ]
        if st.session_state.messages:
            r_cols = st.columns(2)
            for idx, m in enumerate(st.session_state.messages):
                border_color = "#D32F2F" if m['role'] == "story" else "#0277BD"
                icon = "🛡️ 설정 충돌" if m['role'] == "story" else "🏛️ 역사 고증"
                bg_color = "#FFF5F5" if m['role'] == "story" else "#F0F8FF"
                with r_cols[idx % 2]:
                    st.markdown(
                        f"""<div class="moneta-card" style="border-left: 4px solid {border_color}; background-color: {bg_color};"><div style="font-weight:bold; margin-bottom:6px; color:#455A64;">{icon}</div><div style="margin-bottom:8px; font-size:15px; color:#263238;">{m['msg']}</div><div style="background:#FFFFFF; padding:8px 12px; border-radius:4px; font-size:13px; color:#546E7A; border:1px solid #CFD8DC; display:inline-block;">💡 제안: <b>{m['fix']}</b></div></div>""",
                        unsafe_allow_html=True)

    # 기본 텍스트 에디터 (st.text_area)
    content = st.text_area("본문", value=current_doc['content'], height=800, label_visibility="collapsed",
                           key=f"editor_{current_doc['id']}")
    if content != current_doc['content']:
        current_doc['content'] = content


def render_characters():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()
    render_sidebar(proj)
    c1, c2 = st.columns([8, 2])
    with c1:
        st.markdown(f"## 등장인물 <span style='font-size:18px; color:grey'>({len(proj['characters'])})</span>",
                    unsafe_allow_html=True)
    with c2:
        if st.button("＋ 새 인물", type="primary", use_container_width=True):
            add_character_modal(proj)
    st.divider()
    if not proj['characters']:
        st.info("등록된 인물이 없습니다.")
        return
    h1, h2, h3 = st.columns([2, 5, 2])
    h1.caption("이름")
    h2.caption("태그 및 설명")
    h3.caption("관리")
    for char in proj['characters']:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 5, 2])
            with c1:
                if st.button(f"**{char['name']}**", key=f"btn_nm_{char['id']}", use_container_width=True):
                    edit_character_modal(proj, char['id'])
            with c2:
                st.caption(f"#{char['tag']}")
                st.write(char['desc'])
            with c3:
                if st.button("🗑", key=f"del_c_{char['id']}"):
                    proj['characters'].remove(char)
                    st.rerun()


def render_plot():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()
    if "plots" not in proj: proj["plots"] = [{"id": "def", "name": "메인 플롯", "desc": "기본 플롯", "parts": []}]
    render_sidebar(proj)

    plots = proj['plots']
    t_cols = st.columns([len(plots) * 2, 8])
    with t_cols[0]:
        tab_cols = st.columns(len(plots) + 1)
        for i, plot in enumerate(plots):
            with tab_cols[i]:
                btn_type = "primary" if i == st.session_state.active_plot_idx else "secondary"
                if st.button(plot['name'], key=f"tab_{plot['id']}", type=btn_type, use_container_width=True):
                    st.session_state.active_plot_idx = i
                    st.rerun()
        with tab_cols[-1]:
            if st.button("＋", key="add_plot_btn"):
                proj['plots'].append({"id": str(uuid.uuid4()), "name": "새 플롯", "desc": "", "parts": []})
                st.session_state.active_plot_idx = len(proj['plots']) - 1
                st.rerun()
    st.divider()

    if st.session_state.active_plot_idx >= len(plots): st.session_state.active_plot_idx = 0
    curr_plot = plots[st.session_state.active_plot_idx]

    st.markdown(f"### {curr_plot['name']} <span style='font-size:14px; color:#999'>🖊️</span>", unsafe_allow_html=True)
    new_plot_name = st.text_input("플롯 이름", value=curr_plot['name'], key=f"pn_main_{curr_plot['id']}",
                                  label_visibility="collapsed")
    if new_plot_name != curr_plot['name']: curr_plot['name'] = new_plot_name

    new_plot_desc = st.text_input("플롯 설명", value=curr_plot['desc'], key=f"pd_main_{curr_plot['id']}",
                                  placeholder="플롯 설명 입력...", label_visibility="collapsed")
    if new_plot_desc != curr_plot['desc']: curr_plot['desc'] = new_plot_desc

    st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)
    parts = curr_plot['parts']
    cols = st.columns(len(parts) + 1)

    for i, part in enumerate(parts):
        with cols[i]:
            with st.container(border=True):
                h1, h2 = st.columns([5, 1])
                with h1:
                    st.markdown('<div class="part-title-input">', unsafe_allow_html=True)
                    new_name = st.text_input("p_name", value=part['name'], key=f"pnm_{part['id']}",
                                             label_visibility="collapsed")
                    if new_name != part['name']: part['name'] = new_name
                    st.markdown('</div>', unsafe_allow_html=True)
                with h2:
                    with st.popover("⋮"):
                        if st.button("복제", key=f"dup_{part['id']}", use_container_width=True):
                            new_part = part.copy()
                            new_part['id'] = str(uuid.uuid4())
                            curr_plot['parts'].insert(i + 1, new_part)
                            st.rerun()
                        if st.button("삭제", key=f"del_{part['id']}", type="primary", use_container_width=True):
                            curr_plot['parts'].remove(part)
                            st.rerun()
                st.markdown('<div class="part-desc-input">', unsafe_allow_html=True)
                new_desc = st.text_input("p_desc", value=part['desc'], key=f"pdc_{part['id']}",
                                         label_visibility="collapsed", placeholder="설명")
                if new_desc != part['desc']: part['desc'] = new_desc
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('<div class="new-block-input">', unsafe_allow_html=True)
                new_block = st.text_input("new_blk", key=f"nb_{part['id']}", placeholder="+ 새 블록",
                                          label_visibility="collapsed")
                if new_block:
                    part['blocks'].append({"id": str(uuid.uuid4()), "content": new_block})
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("---")
                for block in part['blocks']:
                    st.markdown('<div class="block-card-container">', unsafe_allow_html=True)
                    b1, b2 = st.columns([6, 1])
                    with b1:
                        st.write(block['content'])
                    with b2:
                        with st.popover("⋮"):
                            if st.button("삭제", key=f"rm_b_{block['id']}", type="primary", use_container_width=True):
                                part['blocks'].remove(block)
                                st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
    with cols[-1]:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("＋ 새 파트", key="add_part_btn", use_container_width=True):
            curr_plot['parts'].append({"id": str(uuid.uuid4()), "name": "새 파트", "desc": "", "blocks": []})
            st.rerun()


# =========================================================
# 6. 메인 라우팅
# =========================================================
if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "editor":
    render_editor()
elif st.session_state.page == "characters":
    render_characters()
elif st.session_state.page == "plot":
    render_plot()
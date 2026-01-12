import streamlit as st
import time
import uuid

# =========================================================
# 1. 설정 및 CSS (Novela Layout Sync)
# =========================================================
st.set_page_config(
    page_title="Moneta Studio",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* 1. 배경색: 따뜻한 웜톤 아이보리 */
    .stApp {
        background-color: #FDFBF7;
    }

    /* 2. 에디터 스타일 (명조체 + 종이 질감) */
    div[data-testid="stTextArea"] textarea {
        background-color: #FFFFFF !important;
        border: 1px solid #EAE4DC !important;
        border-radius: 4px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
        padding: 60px 80px !important;
        font-size: 17px !important;
        line-height: 2.1 !important;
        font-family: 'KoPub Batang', 'Times New Roman', serif !important;
        color: #333333 !important;
        height: 800px !important;
    }

    /* 3. [공통] 버튼 스타일 */
    div[data-testid="stButton"] button {
        border-radius: 6px !important;
        border: 1px solid #E0D8D0 !important;
        background-color: white !important;
        color: #5D4037 !important;
        font-weight: 500 !important;
        transition: all 0.2s;
    }

    /* 4. [사이드바 전용] 네비게이션 버튼 스타일 (리스트처럼 보이게) */
    /* 사이드바에 있는 버튼들은 테두리 없이 투명하게, 글자는 왼쪽 정렬 */
    section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        background-color: transparent !important;
        border: none !important;
        text-align: left !important;
        color: #555555 !important;
        box-shadow: none !important;
        padding-left: 0px !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
        background-color: #EFEBE9 !important; /* 살짝 연한 갈색 배경 */
        color: #3E2723 !important;
        padding-left: 8px !important; /* 호버 시 살짝 오른쪽으로 이동 */
    }

    /* 사이드바의 '+' 버튼 같은 작은 아이콘 버튼은 예외로 둘 수 있음 (여기선 통일) */

    /* 5. [메인 화면] Primary 버튼 (밀크 초콜릿색 - 스캔 시작용) */
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #8D6E63 !important; /* Milk Chocolate */
        color: white !important;
        border: none !important;
        text-align: center !important; /* 다시 중앙 정렬 */
        padding-left: auto !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #6D4C41 !important;
        box-shadow: 0 2px 5px rgba(109, 76, 65, 0.2) !important;
    }

    /* 6. 사이드바 배경 및 기타 */
    section[data-testid="stSidebar"] {
        background-color: #F9F8F6 !important;
    }

    /* 검색창 스타일 (검색 아이콘 포함된 느낌) */
    div[data-testid="stTextInput"] input {
        border-radius: 20px !important;
        background-color: #FFFFFF !important;
        border: 1px solid #E0E0E0 !important;
        padding-left: 15px !important;
    }

    /* 결과 카드 디자인 */
    .moneta-card {
        padding: 18px;
        border-radius: 8px;
        background-color: #FFFFFF;
        border: 1px solid #F0EAE6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 12px;
    }

    header {visibility: hidden;}
    .block-container { padding-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. 상태 관리
# =========================================================
if "page" not in st.session_state: st.session_state.page = "home"
if "show_moneta" not in st.session_state: st.session_state.show_moneta = False
if "editor_content" not in st.session_state:
    st.session_state.editor_content = """도시는 검게 물들어 있었다.\n\n공중에는 붉은 달이 떠올랐고, 무너진 건물 사이로 몬스터들의 잔해가 널브러져 있었다. 심연의 군주는 사라졌지만, 세상은 이미 이전과 같지 않았다.\n\n"이제 끝인가요?"\n\n서아라가 다가왔다. 그녀의 눈엔 피로와 안도감이 섞여 있었다. 성훈은 천천히 숨을 내쉬었다. 그의 손에는 '어둠의 계약서'가 남아 있었다.\n\n[시스템 선택지: 새로운 게임 관리자 권한을 수락하시겠습니까?]\n\n"관리자…?"\n\n이제 그는 현실과 게임 사이에 서 있었다."""
if "messages" not in st.session_state: st.session_state.messages = []
if "current_project_id" not in st.session_state: st.session_state.current_project_id = None
if "projects" not in st.session_state:
    st.session_state.projects = [
        {"id": str(uuid.uuid4()), "title": "지옥같은 전쟁에 떨어졌다.", "tags": ["판타지", "전쟁"], "desc": "눈을 떠보니 참호 속이었다...",
         "last_edited": "방금 전"}
    ]


# =========================================================
# 3. 화면 로직
# =========================================================

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
            st.session_state.projects.append({
                "id": str(uuid.uuid4()), "title": title, "desc": desc or "설명 없음",
                "tags": [t.strip() for t in tags.split(",") if t.strip()], "last_edited": "방금 생성됨"
            })
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
                # 홈 화면의 버튼들은 카드 안에 있으므로 일반 버튼 스타일 유지
                if b1.button("작업하기", key=f"open_{p['id']}", use_container_width=True):
                    st.session_state.current_project_id = p['id']
                    st.session_state.page = "editor"
                    st.rerun()
                if b2.button("🗑", key=f"del_{p['id']}", use_container_width=True):
                    st.session_state.projects = [proj for proj in st.session_state.projects if proj['id'] != p['id']]
                    st.rerun()


def render_editor():
    current_proj = next((p for p in st.session_state.projects if p['id'] == st.session_state.current_project_id), None)
    if not current_proj: st.session_state.page = "home"; st.rerun()

    # --- [사이드바: Novela 완벽 레이아웃] ---
    with st.sidebar:
        # 1. 홈으로 버튼 (최상단, 작고 심플하게)
        if st.button("🏠 홈으로", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

        st.markdown(f"## {current_proj['title']}")

        # 2. 검색창 (요청사항 반영)
        st.text_input("검색", placeholder="검색...", label_visibility="collapsed")

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)  # 여백

        # 3. 메뉴 리스트 (세로 배치, 아이콘 포함)
        # CSS로 인해 왼쪽 정렬된 투명 버튼으로 렌더링됨
        st.button("👤  등장인물", use_container_width=True)
        st.button("📅  플롯", use_container_width=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)  # 여백

        # 4. 문서 목록 헤더와 + 버튼
        c_head, c_plus = st.columns([8, 2])
        c_head.caption("문서")
        c_plus.button("➕", key="add_doc_btn")  # 문서 추가 버튼

        # 문서 트리
        # (버튼 텍스트 앞에 아이콘을 붙여 리스트 느낌 강화)
        st.button("📄  프롤로그", key="doc_prologue", use_container_width=True)
        # 현재 선택된 문서는 색상을 달리하거나 아이콘 변경 가능
        st.button("📝  3막 엔딩", key="doc_curr", use_container_width=True)

        # --- [메인 헤더] ---
    col_title, col_moneta = st.columns([8, 2], gap="small")
    with col_title:
        st.markdown("## 3막 엔딩")
    with col_moneta:
        btn_label = "✖ 닫기" if st.session_state.show_moneta else "✨ Moneta 분석"
        btn_type = "secondary" if st.session_state.show_moneta else "primary"

        if st.button(btn_label, type=btn_type, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.show_moneta
            st.rerun()

    # --- [Moneta 패널] ---
    if st.session_state.show_moneta:
        with st.container(border=True):
            c_desc, c_act = st.columns([7, 3], gap="medium")
            with c_desc:
                st.markdown("**🤖 Moneta AI 분석 센터**")
                st.caption("역사 고증(Clio)과 설정 오류(Story Keeper)를 통합 검토합니다.")
            with c_act:
                # Primary 버튼 (밀크초콜릿색)
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
                    st.markdown(f"""
                    <div class="moneta-card" style="border-left: 4px solid {border_color}; background-color: {bg_color};">
                        <div style="font-weight:bold; margin-bottom:6px; color:#455A64;">{icon}</div>
                        <div style="margin-bottom:8px; font-size:15px; color:#263238;">{m['msg']}</div>
                        <div style="background:#FFFFFF; padding:8px 12px; border-radius:4px; font-size:13px; color:#546E7A; border:1px solid #CFD8DC; display:inline-block;">
                            💡 제안: <b>{m['fix']}</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # --- [에디터 본문] ---
    st.text_area("본문", value=st.session_state.editor_content, height=800, label_visibility="collapsed")


if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "editor":
    render_editor()
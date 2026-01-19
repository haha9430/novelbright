import streamlit as st
import sys
from pathlib import Path

# 컴포넌트 임포트
from components.home import render_home
from components.editor import render_editor
from components.universe import render_universe
from components.sidebar import render_sidebar
from components.materials import render_materials

# --------------------------------------------------------------------------
# 1. 초기 설정 (Page Config)
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="NovellBright - AI 웹소설 에디터",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------------------------------
# 2. 세션 상태 초기화 (Session State)
# --------------------------------------------------------------------------

# ✅ [수정됨] 프로젝트 리스트를 빈 배열로 초기화 (시연용 Clean State)
if "projects" not in st.session_state:
    st.session_state.projects = []

if "page" not in st.session_state:
    st.session_state.page = "home"
if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = None
if "current_doc_id" not in st.session_state:
    st.session_state.current_doc_id = None
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# Moneta(분석 도구) 관련 상태
if "show_moneta" not in st.session_state:
    st.session_state.show_moneta = False
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {}
if "sk_analyzed" not in st.session_state:
    st.session_state.sk_analyzed = False
if "clio_analyzed" not in st.session_state:
    st.session_state.clio_analyzed = False

# --------------------------------------------------------------------------
# 3. CSS 스타일 정의
# --------------------------------------------------------------------------

# (1) 공통 CSS
common_css = """
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css");

    html, body, [class*="css"] {
        font-family: 'Pretendard', sans-serif;
    }

    /* 버튼 스타일 통일 */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
    }

    /* Primary 버튼 (노벨라 스타일 초록색) */
    div.stButton > button[type="primary"] {
        background-color: #009688 !important;
        border-color: #009688 !important;
        color: white !important;
    }
    div.stButton > button[type="primary"]:hover {
        background-color: #00796b !important;
        border-color: #00796b !important;
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: transparent !important;
        border-bottom-color: #009688 !important;
        color: #009688 !important;
    }
"""

# (2) 라이트 모드 CSS
light_theme = """
    .stApp { background-color: #f8f9fa; color: #212529; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e9ecef; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea { background-color: #ffffff; color: #212529; }
"""

# (3) 다크 모드 CSS
dark_theme = """
    .stApp { background-color: #1e1e1e; color: #e0e0e0; }
    section[data-testid="stSidebar"] { background-color: #252526; border-right: 1px solid #333333; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea { background-color: #333333; color: #e0e0e0; border-color: #555555; }
    [data-testid="stExpander"], [data-testid="stForm"], .project-card { background-color: #2d2d2d !important; border-color: #444444 !important; color: #e0e0e0 !important; }
    .thumb-container { background-color: #333333 !important; }
"""

selected_css = dark_theme if st.session_state.dark_mode else light_theme

st.markdown(
    f"""
    <style>
        {common_css}
        {selected_css}
        header[data-testid="stHeader"] {{ background-color: transparent !important; z-index: 1; }}

        /* 사이드바 닫았을 때 여는 버튼 스타일링 */
        [data-testid="stSidebarCollapsedControl"] {{
            display: block !important;
            visibility: visible !important;
            color: {"#ffffff" if st.session_state.dark_mode else "#333333"} !important;
            background-color: rgba(128, 128, 128, 0.2);
            border-radius: 50%;
            padding: 4px;
            z-index: 999999 !important;
            left: 20px !important;
            top: 20px !important;
        }}
        [data-testid="stSidebarCollapsedControl"] img {{ width: 24px !important; height: 24px !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# 4. 라우팅 로직 (Routing)
# --------------------------------------------------------------------------
if st.session_state.page == "home":
    render_home()

else:
    # 현재 선택된 프로젝트 찾기
    current_proj = next(
        (p for p in st.session_state.projects if p["id"] == st.session_state.current_project_id),
        None
    )

    # 프로젝트가 없으면 홈으로 리다이렉트
    if not current_proj:
        st.session_state.page = "home"
        st.session_state.current_project_id = None
        st.rerun()

    # 페이지별 렌더링
    if st.session_state.page == "editor":
        render_editor()

    elif st.session_state.page == "universe":
        render_universe()

    elif st.session_state.page == "materials":
        render_materials()

    else:
        st.session_state.page = "home"
        st.rerun()
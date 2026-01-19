import streamlit as st
import sys
from pathlib import Path
# 모듈 경로 설정 (필요 시)
# sys.path.append(str(Path(__file__).parent))

# 컴포넌트 임포트
from components.home import render_home
from components.editor import render_editor
from components.universe import render_universe
from components.sidebar import render_sidebar
from components.materials import render_materials

# --------------------------------------------------------------------------
# 1. 초기 설정 (Page Config & Session State)
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="NovellBright - AI 웹소설 에디터",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# [수정] 세션 상태 초기화 (빠진 변수들 추가함)
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

# ✅ [추가됨] Moneta(분석 도구) 관련 상태 초기화
if "show_moneta" not in st.session_state:
    st.session_state.show_moneta = False  # 패널 열림/닫힘 상태
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {}  # 분석 결과 저장소
if "sk_analyzed" not in st.session_state:
    st.session_state.sk_analyzed = False
if "clio_analyzed" not in st.session_state:
    st.session_state.clio_analyzed = False

# --------------------------------------------------------------------------
# 2. CSS 스타일 정의 (다크모드 / 라이트모드 / 공통 / 사이드바 버튼 복구)
# --------------------------------------------------------------------------

# (1) 공통 CSS
common_css = """
    /* 폰트 적용 */
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
    div.stButton > button[kind="primary"] {
        background-color: #009688 !important;
        border-color: #009688 !important;
        color: white !important;
    }
    div.stButton > button[kind="primary"]:hover {
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
    /* 전체 배경 및 텍스트 */
    .stApp {
        background-color: #f8f9fa;
        color: #212529;
    }
    /* 사이드바 배경 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e9ecef;
    }
    /* 입력창 배경 */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background-color: #ffffff;
        color: #212529;
    }
"""

# (3) 다크 모드 CSS
dark_theme = """
    /* 전체 배경 및 텍스트 */
    .stApp {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    /* 사이드바 배경 */
    section[data-testid="stSidebar"] {
        background-color: #252526;
        border-right: 1px solid #333333;
    }
    /* 입력창 배경 */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background-color: #333333;
        color: #e0e0e0;
        border-color: #555555;
    }
    /* 카드(컨테이너) 배경 어둡게 */
    [data-testid="stExpander"], [data-testid="stForm"], .project-card {
        background-color: #2d2d2d !important;
        border-color: #444444 !important;
        color: #e0e0e0 !important;
    }
    /* 다크모드일 때 아이콘/이미지 배경 처리 */
    .thumb-container {
        background-color: #333333 !important;
    }
"""

# 현재 모드에 따른 CSS 선택
selected_css = dark_theme if st.session_state.dark_mode else light_theme

# CSS 렌더링
st.markdown(
    f"""
    <style>
        /* 1. 공통 및 테마 적용 */
        {common_css}
        {selected_css}

        /* 2. 헤더 투명화 (UI 깔끔하게) */
        header[data-testid="stHeader"] {{
            background-color: transparent !important;
            z-index: 1;
        }}

        /* 3. [핵심] 사이드바 닫았을 때 여는 버튼(화살표) 강제 표시 & 스타일링 */
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

        /* 모바일 등에서 버튼 크기 확보 */
        [data-testid="stSidebarCollapsedControl"] img {{
            width: 24px !important;
            height: 24px !important;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# 3. 라우팅 로직 (Routing)
# --------------------------------------------------------------------------

# (1) 홈 화면
if st.session_state.page == "home":
    render_home()

# (2) 프로젝트 작업 화면
else:
    current_proj = next(
        (p for p in st.session_state.projects if p["id"] == st.session_state.current_project_id),
        None
    )

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
        # ✅ [수정됨] 기존의 임시 문구 코드를 지우고, 함수 호출로 변경!
        render_materials()

    else:
        st.session_state.page = "home"
        st.rerun()
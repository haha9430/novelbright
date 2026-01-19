import sys
import os

from components.universe import render_universe
# 현재 파일(main.py)이 있는 폴더를 파이썬 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))  # .../PythonProject/frontend
project_root = os.path.dirname(current_dir)               # .../PythonProject
sys.path.append(current_dir)

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
import uuid

from components.home import render_home
from components.editor import render_editor
from components.characters import render_characters
from components.plot import render_plot
from components.materials import render_materials

# =========================================================
# 1. 설정 및 상태 초기화
# =========================================================
st.set_page_config(page_title="Moneta Studio", page_icon="✍️", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
<style>
    .stApp { background-color: #FDFBF7; }
    .stQuill { background-color: #FFFFFF !important; border: 1px solid #EAE4DC !important; border-radius: 4px !important; padding: 20px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important; }
    div[data-testid="stModal"] textarea { padding: 10px 15px !important; font-family: sans-serif; font-size: 14px; }
    div[data-testid="stButton"] button { border-radius: 6px !important; border: 1px solid #E0D8D0 !important; background-color: white !important; color: #5D4037 !important; transition: all 0.2s; }
    div[data-testid="stButton"] button:hover { background-color: #FAF5F0 !important; border-color: #BCAAA4 !important; }
    div[data-testid="stButton"] button[kind="primary"] { background-color: #8D6E63 !important; color: white !important; border: none !important; }
    div[data-testid="stButton"] button[kind="primary"]:hover { background-color: #6D4C41 !important; }
    section[data-testid="stSidebar"] { background-color: #F9F8F6 !important; }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button { background-color: transparent !important; border: none !important; text-align: left !important; padding-left: 8px !important; box-shadow: none !important; color: #555555 !important; }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover { background-color: #EBEBEB !important; color: #000000 !important; font-weight: 500 !important; }
    .doc-title-input input { font-family: 'KoPub Batang', serif; font-size: 34px !important; font-weight: 700 !important; color: #333 !important; background-color: transparent !important; border: none !important; padding: 0px !important; }
    .doc-title-input input:focus { box-shadow: none !important; }
    .ghost-input input { background: transparent !important; border: none !important; font-weight: bold; color: #333; }
    .ghost-input input:focus { background: #f9f9f9 !important; border-bottom: 2px solid #FF6B6B !important; }
    .moneta-card { padding: 15px; border-radius: 8px; background: white; border: 1px solid #eee; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    div[data-testid="stVerticalBlockBorderWrapper"] { border: none !important; padding: 0px !important; overflow-x: auto !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] { width: max-content !important; min-width: 100%; }
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="column"] { width: 300px !important; min-width: 300px !important; flex: 0 0 300px !important; margin-right: 12px; }
</style>
""",
    unsafe_allow_html=True,
)

if "page" not in st.session_state: st.session_state.page = "home"
if "show_moneta" not in st.session_state: st.session_state.show_moneta = False
if "dark_mode" not in st.session_state: st.session_state.dark_mode = False

# 기존 상태 변수들
if "current_project_id" not in st.session_state: st.session_state.current_project_id = None
if "analysis_results" not in st.session_state: st.session_state.analysis_results = {}
if "current_doc_id" not in st.session_state: st.session_state.current_doc_id = None
if "active_plot_idx" not in st.session_state: st.session_state.active_plot_idx = 0
if "selected_block_id" not in st.session_state: st.session_state.selected_block_id = None
if "is_adding_part" not in st.session_state: st.session_state.is_adding_part = False
if "selected_material_id" not in st.session_state: st.session_state.selected_material_id = None

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
            "documents": [{"id": "doc1", "title": "프롤로그", "content": "<p>눈을 떠보니...</p>", "episode_no": 1}],
            "plots": [{"id": "def", "name": "메인 플롯", "desc": "기본 플롯", "parts": []}]
        }
    ]

# =========================================================
# 2. CSS 스타일링 (라이트/다크 분기)
# =========================================================

# 공통 CSS
common_css = """
    /* 상단 헤더 숨김 */
    header {visibility: hidden;}
    /* 상단 여백 최소화 */
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }

    div[data-testid="stModal"] textarea { padding: 10px 15px !important; font-family: sans-serif; font-size: 14px; }
    .doc-title-input input { font-family: 'KoPub Batang', serif; font-size: 34px !important; font-weight: 700 !important; background-color: transparent !important; border: none !important; padding: 0px !important; }
    .doc-title-input input:focus { box-shadow: none !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border: none !important; padding: 0px !important; overflow-x: auto !important; }
"""

# 🌞 라이트 모드 CSS
light_theme = """
    .stApp { background-color: #FDFBF7; color: #333; }
    .stQuill { background-color: #FFFFFF !important; border: 1px solid #EAE4DC !important; color: #333 !important; }
    section[data-testid="stSidebar"] { background-color: #F9F8F6 !important; }
    div[data-testid="stButton"] button { background-color: white !important; color: #5D4037 !important; border: 1px solid #E0D8D0 !important; }
    div[data-testid="stButton"] button:hover { background-color: #FAF5F0 !important; border-color: #BCAAA4 !important; }
    .moneta-card { background: white; border: 1px solid #eee; color: #333; }
    .doc-title-input input { color: #333 !important; }
"""

# 🌜 다크 모드 CSS (수정)
dark_theme = """
    /* 1. 전체 앱 배경 및 글자색 */
    .stApp { background-color: #1E1E1E; color: #E0E0E0; }

    /* 2. 사이드바 텍스트 강제 색상 변경 */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] div, 
    section[data-testid="stSidebar"] p { 
        color: #E0E0E0 !important; 
    }

    section[data-testid="stSidebar"] { background-color: #252526 !important; border-right: 1px solid #333; }

    /* 3. 입력창 스타일 (검색창 포함) */
    input, textarea, .stTextInput > div > div { 
        background-color: #2D2D30 !important; 
        color: #E0E0E0 !important; 
        border-color: #444 !important; 
    }

    /* 4. [수정] 팝오버(점 3개) 버튼 스타일 - 평소 상태 */
    div[data-testid="stPopover"] > button {
        background-color: transparent !important; /* 배경 투명하게 */
        color: #E0E0E0 !important;
        border: 1px solid #444 !important;
    }

    /* 팝오버 버튼 마우스 올렸을 때 */
    div[data-testid="stPopover"] > button:hover {
        background-color: #444 !important;
        border-color: #888 !important;
    }

    /* 5. [수정] 모달(Dialog) 창 스타일 - 배경을 어둡게! */
    div[role="dialog"] {
        background-color: #2D2D30 !important; /* 모달 전체 배경 */
    }

    div[role="dialog"] > div {
        background-color: #2D2D30 !important; /* 모달 내부 컨텐츠 배경 */
        color: #E0E0E0 !important;
    }

    /* 모달 내부 텍스트들 */
    div[role="dialog"] h2, 
    div[role="dialog"] p, 
    div[role="dialog"] label,
    div[role="dialog"] div {
        color: #E0E0E0 !important;
    }

    /* 모달 닫기(X) 버튼 */
    div[role="dialog"] button[aria-label="Close"] {
        color: #E0E0E0 !important;
    }

    /* 6. 일반 버튼 스타일 */
    div[data-testid="stButton"] button { 
        background-color: #333333 !important; 
        color: #E0E0E0 !important; 
        border: 1px solid #444 !important; 
    }
    div[data-testid="stButton"] button:hover { 
        background-color: #444444 !important; 
        border-color: #666 !important; 
    }
    div[data-testid="stButton"] button p { color: #E0E0E0 !important; }

    /* 7. 기타 커스텀 요소 */
    .moneta-card { background: #2D2D30 !important; border: 1px solid #444 !important; color: #E0E0E0 !important; }
    .doc-title-input input { color: #E0E0E0 !important; }
    .streamlit-expanderHeader { background-color: #2D2D30 !important; color: #E0E0E0 !important; }
    div[data-testid="stMarkdownContainer"] p { color: #E0E0E0 !important; }
"""

selected_css = dark_theme if st.session_state.dark_mode else light_theme
st.markdown(
    f"""
    <style>
        /* 1. 공통 CSS 및 선택된 테마(다크/라이트) 적용 */
        {common_css}
        {selected_css}

        /* 2. 헤더 투명화 등 추가 스타일 */
        header[data-testid="stHeader"] {{
            background-color: transparent !important;
            z-index: 1;
        }}

        /* 3. 사이드바 열기 버튼 강제 표시 */
        section[data-testid="stSidebar"] > div > div:nth-child(2) {{
            /* Streamlit 버전에 따라 다를 수 있음 */
        }}

        [data-testid="stSidebarCollapsedControl"] {{
            display: block !important;
            color: #ffffff !important;
            background-color: rgba(100, 100, 100, 0.5);
            border-radius: 5px;
            padding: 2px;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# 3. Main Routing
# =========================================================
if st.session_state.page == "home":
    render_home()

elif st.session_state.page == "editor":
    render_editor()

elif st.session_state.page == "universe":
    # [수정] characters, plot 대신 universe로 통합
    # render_universe 내부에서 render_sidebar를 부릅니다.
    render_universe()

elif st.session_state.page == "materials":
    render_materials()

elif st.session_state.page == "characters":
    render_characters()
elif st.session_state.page == "plot":
    render_plot()
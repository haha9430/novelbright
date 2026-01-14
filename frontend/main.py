import sys
import os

# [핵심] 현재 파일(main.py)이 있는 폴더를 파이썬 경로에 추가
# 이걸 해줘야 components 폴더 안에서도 api나 common을 잘 찾습니다.
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import streamlit as st
import uuid

# [수정됨] 불필요한 'from api import save_document' 삭제함
# 필요한 컴포넌트들만 불러옵니다.
from components.home import render_home
from components.editor import render_editor
from components.characters import render_characters
from components.plot import render_plot
from components.materials import render_materials

# =========================================================
# 1. 설정 및 CSS
# =========================================================
st.set_page_config(page_title="Moneta Studio", page_icon="✍️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
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

# 더미 데이터 (백엔드 연결 전용)
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
# 3. Main Routing
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
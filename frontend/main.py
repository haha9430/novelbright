import streamlit as st
from frontend.api import save_document
from frontend.components.sidebar import render_sidebar
from frontend.components.editor import render_editor_area
from frontend.components.moneta import render_moneta_panel

# 페이지 설정
st.set_page_config(layout="wide", page_title="NovelBright")

# 초기 세션 상태 설정
if "analysis_results" not in st.session_state: st.session_state.analysis_results = {}
if "show_moneta" not in st.session_state: st.session_state.show_moneta = False

def main():
    # 1. 사이드바 렌더링 & 현재 작업중인 문서 가져오기
    project, doc = render_sidebar()

    if not project:
        st.title("👈 왼쪽에서 프로젝트를 선택하거나 만들어주세요.")
        return

    if not doc:
        st.title(f"{project['name']} 프로젝트")
        st.info("👈 문서를 선택하거나 새로 만들어주세요.")
        return

    # 2. 에디터 영역 (본문과 변경된 제목을 받아옴)
    content, new_title = render_editor_area(doc)

    # 3. 모네타(AI) 패널
    render_moneta_panel(doc, content)

    # 4. 저장 버튼 (사이드바 하단에 배치하거나 에디터 하단에 배치)
    with st.sidebar:
        st.divider()
        if st.button("💾 원고 저장하기", type="primary", use_container_width=True):
            if save_document(doc['id'], new_title, content):
                st.toast("저장 완료!", icon="✅")

if __name__ == "__main__":
    main()
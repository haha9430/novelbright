import streamlit as st
import uuid
from components.common import get_current_project
from components.sidebar import render_sidebar
from components.characters import render_characters

# 파일 처리 및 API 모듈 임포트 (characters.py와 동일하게 처리)
try:
    from api import ingest_file_to_backend
    from app.common.file_input import FileProcessor
except ImportError:
    def ingest_file_to_backend(*args, **kwargs):
        return True


    class FileProcessor:
        @staticmethod
        def load_file_content(file): return "Dummy Content"


def render_universe():
    # 1. 프로젝트 로드
    proj = get_current_project()
    if not proj:
        st.error("프로젝트를 불러올 수 없습니다.")
        st.session_state.page = "home"
        st.rerun()
        return

    # 사이드바 렌더링
    render_sidebar(proj)

    # 데이터 초기화
    if "worldview" not in proj: proj["worldview"] = ""
    # history(연표)는 삭제됨

    # 2. 헤더
    st.title(f"🌍 {proj['title']} - 설정")
    st.caption("작품의 등장인물, 세계관, 그리고 화별 플롯(요약)을 관리합니다.")

    # ---------------------------------------------------------
    # 3. 탭 구성 (등장인물 / 세계관 / 플롯)
    # ---------------------------------------------------------
    tab_char, tab_world, tab_plot = st.tabs(["👤 등장인물", "🗺️ 세계관", "📌 플롯 (요약)"])

    # (1) 등장인물 탭
    with tab_char:
        render_characters(proj)

    # (2) 세계관 탭
    with tab_world:
        _render_worldview_tab(proj)

    # (3) 플롯 탭 (화별 요약)
    with tab_plot:
        _render_plot_tab(proj)


# ==============================================================================
# 내부 렌더링 함수들
# ==============================================================================

def _render_worldview_tab(proj):
    """세계관 설정 탭: 텍스트 직접 입력 + 파일 업로드"""

    # [추가됨] 상단: 파일로 세계관 추가하기
    with st.expander("📂 파일로 세계관 자료 추가하기", expanded=False):
        st.markdown("세계관 설정이 담긴 텍스트, PDF 문서를 업로드하여 AI에게 학습시킵니다.")
        uploaded_file = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"], key="world_uploader")

        if uploaded_file and st.button("🚀 세계관 분석 및 추가", use_container_width=True):
            with st.spinner("파일을 분석하여 세계관 DB에 저장 중입니다..."):
                try:
                    content = FileProcessor.load_file_content(uploaded_file)
                    if content and not content.startswith("[Error]"):
                        # type="worldview" 로 전송
                        success = ingest_file_to_backend(content, "worldview")
                        if success:
                            st.success("세계관 자료가 성공적으로 추가되었습니다!")
                            # 필요하다면 텍스트 에디터에 내용을 덧붙일 수도 있음
                            # proj["worldview"] += f"\n\n[파일 추가됨: {uploaded_file.name}]\n{content[:200]}..."
                        else:
                            st.error("서버 전송 실패")
                    else:
                        st.error("파일 내용을 읽을 수 없습니다.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")

    st.divider()

    # 하단: 세계관 텍스트 직접 편집
    st.subheader("세계관 설명 (직접 입력)")
    with st.container(border=True):
        world_text = st.text_area(
            "이 작품의 규칙, 배경, 분위기, 기술/마법 체계 등을 기록하세요.",
            value=proj.get("worldview", ""),
            height=400,
            key="worldview_input"
        )

        if world_text != proj.get("worldview", ""):
            proj["worldview"] = world_text


def _render_plot_tab(proj):
    """플롯 탭: 각 에피소드(문서)별 AI 요약 출력"""

    st.subheader("스토리 요약")
    st.caption("각 화의 내용이 자동으로 요약되어 표시되는 공간입니다.")

    docs = proj.get("documents", [])

    if not docs:
        st.info("아직 생성된 문서(에피소드)가 없습니다.")
        return

    # 각 문서(에피소드)를 순회하며 요약 표시
    for i, doc in enumerate(docs):
        # 문서에 summary 필드가 없으면 초기화
        if "summary" not in doc:
            doc["summary"] = ""

        with st.container(border=True):
            # 헤더: 문서 제목
            st.markdown(f"#### 📄 {doc['title']}")

            # 내용: 요약문 (백엔드 출력용이므로 보통 읽기 전용 느낌이지만, 수정 가능하게 배치)
            # 만약 백엔드 연동이 되면 여기에 doc['summary']가 자동으로 채워져 있을 것임.
            summary_text = st.text_area(
                label="AI 요약 내용",
                value=doc["summary"],
                height=150,
                key=f"plot_summary_{doc['id']}",
                placeholder="아직 요약된 내용이 없습니다. (글을 작성하면 AI가 자동으로 요약합니다)"
            )

            # 수정 사항 저장
            if summary_text != doc["summary"]:
                doc["summary"] = summary_text
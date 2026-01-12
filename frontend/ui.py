import streamlit as st
import time
import uuid  # 작품을 위한 고유 ID 생성

# =========================================================
# 1. 기본 설정
# =========================================================
st.set_page_config(
    page_title="Moneta - Web Novel Editor",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# [상태 초기화] DB 대용 (Session State)
# ---------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "show_moneta" not in st.session_state:
    st.session_state.show_moneta = False
if "editor_content" not in st.session_state:
    st.session_state.editor_content = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# [중요] 프로젝트 데이터 초기화 (없으면 기본 예시 1개만 생성)
if "projects" not in st.session_state:
    st.session_state.projects = [
        {
            "id": str(uuid.uuid4()),
            "title": "로그아웃이 안 되는 헌터",
            "tags": ["웹소설", "헌터물"],
            "desc": "이성훈(32세)은 인기 VR MMORPG...",
            "last_edited": "방금 전"
        }
    ]

# [중요] 현재 선택된 프로젝트 정보
if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = None


# =========================================================
# 2. 화면: 홈 (내 작품 목록)
# =========================================================
def render_home():
    st.title("내 작품")
    st.markdown("---")

    # --- [새 작품 추가 로직] ---
    with st.sidebar:
        st.header("작업 공간")
        # 폼(Form)을 써서 엔터 키로 제출되게 함
        with st.form("new_project_form"):
            st.write("➕ **새 작품 만들기**")
            new_title = st.text_input("제목", placeholder="작품 제목 입력")
            new_desc = st.text_input("한 줄 소개", placeholder="간략한 설명")
            new_tags = st.text_input("태그", placeholder="예: 판타지, 로맨스 (쉼표 구분)")

            submitted = st.form_submit_button("생성하기", type="primary")

            if submitted:
                if not new_title:
                    st.error("제목을 입력해주세요!")
                else:
                    # 데이터 추가 (Append)
                    st.session_state.projects.append({
                        "id": str(uuid.uuid4()),
                        "title": new_title,
                        "desc": new_desc if new_desc else "설명 없음",
                        "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
                        "last_edited": "방금 생성됨"
                    })
                    st.success(f"'{new_title}' 생성 완료!")
                    time.sleep(0.5)
                    st.rerun()  # 화면 새로고침

    # --- [프로젝트 목록 렌더링] ---
    if not st.session_state.projects:
        st.info("아직 생성된 작품이 없습니다. 사이드바에서 새 작품을 만들어보세요!")
        return

    # 카드 그리드 배치
    cols = st.columns(3)
    for i, p in enumerate(st.session_state.projects):
        with cols[i % 3]:
            with st.container(border=True):
                # 상단: 제목과 태그
                st.subheader(p["title"])
                if p["tags"]:
                    st.caption(" ".join([f"#{t}" for t in p["tags"]]))
                else:
                    st.caption("#태그없음")

                # 내용
                st.text(p["desc"][:40] + ("..." if len(p["desc"]) > 40 else ""))
                st.caption(f"수정: {p['last_edited']}")

                # 하단 버튼 그룹 (편집 / 삭제)
                c_edit, c_del = st.columns([3, 1])

                with c_edit:
                    if st.button("편집하기", key=f"btn_edit_{p['id']}", type="primary", use_container_width=True):
                        st.session_state.current_project_id = p['id']
                        st.session_state.page = "editor"
                        st.rerun()

                with c_del:
                    if st.button("🗑", key=f"btn_del_{p['id']}", use_container_width=True):
                        # 리스트에서 해당 ID를 가진 항목 제거
                        st.session_state.projects = [
                            proj for proj in st.session_state.projects if proj['id'] != p['id']
                        ]
                        st.rerun()


# =========================================================
# 3. 화면: 에디터
# =========================================================
def render_editor():
    # 현재 어떤 프로젝트를 수정 중인지 확인
    current_proj = next((p for p in st.session_state.projects if p['id'] == st.session_state.current_project_id), None)

    # 혹시 프로젝트가 삭제되었다면 홈으로 튕김
    if not current_proj:
        st.session_state.page = "home"
        st.rerun()

    # --- [상단 헤더] ---
    c1, c2, c3 = st.columns([1, 8, 2])
    with c1:
        if st.button("← 홈"):
            st.session_state.page = "home"
            st.rerun()
    with c2:
        # 동적 제목 표시
        st.markdown(f"### {current_proj['title']} (3막 엔딩)")
    with c3:
        btn_label = "✖ 닫기" if st.session_state.show_moneta else "✨ Moneta 분석"
        btn_type = "secondary" if st.session_state.show_moneta else "primary"

        if st.button(btn_label, type=btn_type, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.show_moneta
            st.rerun()

    st.divider()

    # --- [좌측 사이드바] ---
    with st.sidebar:
        st.caption("문서 목록")
        with st.expander("📂 1막", expanded=False):
            st.button("📄 1화: 시작", key="d1")
        with st.expander("📂 3막", expanded=True):
            st.button("📄 3막 엔딩", key="d2", type="primary")
            st.button("📄 리서치 자료", key="d3")
        st.divider()
        st.button("⚙️ 설정")

    # --- [Moneta 패널] ---
    if st.session_state.show_moneta:
        with st.container(border=True):
            m_col1, m_col2 = st.columns([1, 2])
            with m_col1:
                st.markdown("#### 🤖 Moneta 분석 센터")
                st.caption("설정 오류와 역사적 고증을 검토합니다.")
                if st.button("🔄 지금 분석 실행", type="primary", use_container_width=True):
                    st.session_state.messages = [
                        {"type": "error", "title": "설정 충돌", "msg": "심연의 군주는 소멸했습니다.", "fix": "잔재로 변경"},
                        {"type": "info", "title": "Clio 고증", "msg": "나폴레옹 사망은 1821년입니다.", "fix": "연도 수정"}
                    ]
                    st.toast("분석 완료!")
            with m_col2:
                if st.session_state.messages:
                    for msg in st.session_state.messages:
                        kind = "error" if msg['type'] == 'error' else "info"
                        with st.status(f"[{msg['title']}] {msg['msg']}", state=kind, expanded=True):
                            st.write(f"👉 제안: {msg['fix']}")
                            c_a, c_b = st.columns(2)
                            c_a.button("수정 적용", key=f"fix_{msg['title']}")
                            c_b.button("무시", key=f"ign_{msg['title']}")
                else:
                    st.info("분석 버튼을 눌러주세요.")

    # --- [에디터 본문] ---
    text_input = st.text_area(
        "본문 작성",
        value=st.session_state.editor_content,
        height=600,
        label_visibility="collapsed",
        placeholder="여기에 소설을 작성하세요..."
    )
    st.session_state.editor_content = text_input


# =========================================================
# 4. 메인 실행
# =========================================================
if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "editor":
    render_editor()
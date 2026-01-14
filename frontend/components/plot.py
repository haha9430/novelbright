import streamlit as st
import uuid
from components.common import get_current_project
from components.sidebar import render_sidebar


def render_plot():
    # 1. 현재 프로젝트 가져오기
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    # 2. 데이터 초기화 (플롯 데이터가 없으면 기본값 생성)
    if "plots" not in proj:
        proj["plots"] = [{"id": "def", "name": "메인 플롯", "desc": "", "parts": []}]

    # 인덱스 안전장치 (삭제 등으로 인덱스가 범위를 벗어났을 경우)
    if st.session_state.active_plot_idx >= len(proj['plots']):
        st.session_state.active_plot_idx = 0

    if "selected_block_id" not in st.session_state:
        st.session_state.selected_block_id = None

    # 3. CSS 적용 (가로 스크롤을 위한 핵심 스타일)
    st.markdown("""<style>div[data-testid="stVerticalBlockBorderWrapper"] { overflow-x: auto !important; }</style>""",
                unsafe_allow_html=True)

    # 4. 사이드바 렌더링
    render_sidebar(proj)

    # 5. 상단 탭 (플롯 선택)
    plots = proj['plots']
    with st.container():
        cols = st.columns(len(plots) + 1)
        for i, p in enumerate(plots):
            with cols[i]:
                # 현재 선택된 플롯은 primary 색상으로 표시
                btn_type = "primary" if i == st.session_state.active_plot_idx else "secondary"
                if st.button(p['name'], key=f"pt_{p['id']}", type=btn_type, use_container_width=True):
                    st.session_state.active_plot_idx = i
                    st.rerun()

        # 플롯 추가 버튼
        with cols[-1]:
            if st.button("＋", key="add_pl"):
                proj['plots'].append({"id": str(uuid.uuid4()), "name": "새 플롯", "parts": []})
                st.session_state.active_plot_idx = len(proj['plots']) - 1
                st.rerun()

    st.divider()

    # 현재 활성화된 플롯 데이터
    curr_plot = plots[st.session_state.active_plot_idx]

    # 6. 플롯 정보 편집 (이름, 삭제, 줄거리)
    c1, c2 = st.columns([8, 1])
    with c1:
        new_pn = st.text_input("플롯 이름", value=curr_plot['name'], key=f"pnn_{curr_plot['id']}",
                               label_visibility="collapsed")
        if new_pn != curr_plot['name']:
            curr_plot['name'] = new_pn
    with c2:
        # 플롯이 2개 이상일 때만 삭제 가능
        if len(plots) > 1 and st.button("🗑", key="del_pl"):
            proj['plots'].pop(st.session_state.active_plot_idx)
            st.session_state.active_plot_idx = 0
            st.rerun()

    st.markdown("###### 📜 전체 줄거리")
    story_k = f"s_{curr_plot['id']}"
    if 'story' not in curr_plot: curr_plot['story'] = ""
    new_s = st.text_area("줄거리", value=curr_plot['story'], key=story_k, height=100, label_visibility="collapsed")
    if new_s != curr_plot['story']:
        curr_plot['story'] = new_s

    st.markdown("<br>", unsafe_allow_html=True)

    # 7. 선택된 블록 찾기 (인스펙터 표시용)
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

    # 8. 레이아웃 분할 (보드 vs 인스펙터)
    if selected_block:
        main_cols = st.columns([7, 3])
        col_board_area = main_cols[0]
        col_inspector = main_cols[1]
    else:
        col_board_area = st.container()

    # 9. 보드 영역 (가로 스크롤 되는 파트들)
    with col_board_area:
        with st.container(border=True):
            cols = st.columns(len(curr_plot['parts']) + 1)

            # 각 파트(Part) 렌더링
            for i, part in enumerate(curr_plot['parts']):
                with cols[i]:
                    with st.container(border=True):
                        # 파트 헤더 (이름 및 메뉴)
                        h1, h2 = st.columns([4, 1])
                        with h1:
                            st.markdown('<div class="ghost-input">', unsafe_allow_html=True)
                            np = st.text_input(f"pn_{part['id']}", value=part['name'], label_visibility="collapsed")
                            if np != part['name']: part['name'] = np
                            st.markdown('</div>', unsafe_allow_html=True)
                        with h2:
                            with st.popover("⋮"):
                                # 왼쪽 이동
                                if st.button("⬅️", key=f"l_{part['id']}"):
                                    if i > 0:
                                        curr_plot['parts'][i], curr_plot['parts'][i - 1] = curr_plot['parts'][i - 1], \
                                        curr_plot['parts'][i]
                                        st.rerun()
                                # 오른쪽 이동
                                if st.button("➡️", key=f"r_{part['id']}"):
                                    if i < len(curr_plot['parts']) - 1:
                                        curr_plot['parts'][i], curr_plot['parts'][i + 1] = curr_plot['parts'][i + 1], \
                                        curr_plot['parts'][i]
                                        st.rerun()
                                # 파트 삭제
                                if st.button("🗑", key=f"dp_{part['id']}"):
                                    curr_plot['parts'].remove(part)
                                    st.rerun()

                        st.markdown("---")

                        # 블록(Block) 리스트 렌더링
                        for block in part['blocks']:
                            txt = block['content'] if block['content'] else "내용 없음"
                            is_sel = (block['id'] == st.session_state.selected_block_id)
                            # 블록 버튼 (클릭 시 선택됨)
                            if st.button(txt[:20] + ("..." if len(txt) > 20 else ""), key=f"b_{block['id']}",
                                         type="primary" if is_sel else "secondary", use_container_width=True):
                                st.session_state.selected_block_id = block['id']
                                st.rerun()

                        # 블록 추가 버튼
                        if st.button("＋ 블록", key=f"ab_{part['id']}"):
                            part['blocks'].append({"id": str(uuid.uuid4()), "content": ""})
                            st.rerun()

            # 파트 추가 컬럼 (맨 오른쪽)
            with cols[-1]:
                if not st.session_state.is_adding_part:
                    if st.button("＋ 파트 추가"):
                        st.session_state.is_adding_part = True
                        st.rerun()
                else:
                    with st.container(border=True):
                        np_val = st.text_input("새 파트명")
                        c1, c2 = st.columns(2)
                        if c1.button("취소"):
                            st.session_state.is_adding_part = False
                            st.rerun()
                        if c2.button("추가"):
                            curr_plot['parts'].append(
                                {"id": str(uuid.uuid4()), "name": np_val if np_val else "새 파트", "blocks": []})
                            st.session_state.is_adding_part = False
                            st.rerun()

    # 10. 인스펙터 영역 (오른쪽 패널)
    if selected_block and 'col_inspector' in locals():
        with col_inspector:
            with st.container(border=True):
                # 헤더
                h1, h2 = st.columns([1, 8])
                with h1:
                    if st.button("✕", key="close_insp"):
                        st.session_state.selected_block_id = None
                        st.rerun()
                with h2:
                    st.markdown(
                        f'<div style="color:#888; font-size:13px; margin-top:5px">↳ <b>{parent_part["name"]}</b></div>',
                        unsafe_allow_html=True)

                # 옵션 (복제, 삭제)
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

                # 내용 편집
                new_content = st.text_area("내용", value=selected_block.get('content', ''), height=200,
                                           key=f"ed_c_{selected_block['id']}")
                if new_content != selected_block.get('content', ''):
                    selected_block['content'] = new_content

                # 등장인물 연결
                st.caption("등장인물")
                char_opts = [c['name'] for c in proj.get('characters', [])]
                current_chars = [c for c in selected_block.get('characters', []) if c in char_opts]
                new_chars = st.multiselect("인물 선택", options=char_opts, default=current_chars,
                                           key=f"ed_ch_{selected_block['id']}")
                if new_chars != current_chars:
                    selected_block['characters'] = new_chars

                # 관련 문서 연결
                st.caption("관련 문서")
                doc_opts = [d['title'] for d in proj.get('documents', [])]
                current_docs = [d for d in selected_block.get('docs', []) if d in doc_opts]
                new_docs = st.multiselect("문서 선택", options=doc_opts, default=current_docs,
                                          key=f"ed_doc_{selected_block['id']}")
                if new_docs != current_docs:
                    selected_block['docs'] = new_docs
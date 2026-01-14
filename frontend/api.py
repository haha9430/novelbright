# frontend/api.py
import requests
import streamlit as st

BASE_URL = "http://127.0.0.1:8000"

def save_document_api(doc_id, title, content):
    try:
        payload = {"doc_id": doc_id, "title": title, "content": content}
        res = requests.post(f"{BASE_URL}/documents/save", json=payload)
        return res.status_code == 200
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False


# [수정] sensitivity 인자 추가 (기본값 5)
def analyze_text_api(doc_id, content, episode_no=1, sensitivity=5, modules=None):
    """
    AI 분석 요청 (민감도 포함)
    """
    try:
        if modules is None:
            modules = ["storykeeper", "clio"]

        payload = {
            "doc_id": doc_id,
            "content": content,
            "episode_no": int(episode_no),
            "sensitivity": int(sensitivity),  # [NEW] 값 전송
            "modules": modules
        }

        res = requests.post(f"{BASE_URL}/analyze/text", json=payload)

        if res.status_code == 200:
            return res.json()
        else:
            st.error(f"오류: {res.text}")
            return []
    except Exception as e:
        st.error(f"연결 실패: {e}")
        return []

def save_material_api(material_data):
    try:
        requests.post(f"{BASE_URL}/materials/save", json=material_data)
        return True
    except:
        return False

def delete_material_api(material_id):
    try:
        requests.delete(f"{BASE_URL}/materials/{material_id}")
        return True
    except:
        return False


def save_plot_api(plot_id, name, description):
    """
    플롯(줄거리) 저장 요청
    """
    try:
        payload = {
            "plot_id": plot_id,
            "name": name,
            "description": description
        }
        # 백엔드 엔드포인트는 /plots/save 라고 가정 (백엔드 팀원과 확인 필요)
        # 현재는 예시로 성공 처리만 함
        # res = requests.post(f"{BASE_URL}/plots/save", json=payload)

        # 임시 성공 처리 (백엔드 구현 전까지 에러 안 나게)
        return True

    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False
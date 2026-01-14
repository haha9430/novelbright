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


def analyze_text_api(doc_id, content, modules=None):
    """
    AI 분석 요청 (modules: ['storykeeper'] 또는 ['clio'] 또는 둘 다)
    """
    try:
        # modules가 없으면 기본적으로 둘 다 포함 (혹은 백엔드 기본값 따름)
        if modules is None:
            modules = ["storykeeper", "clio"]

        payload = {
            "doc_id": doc_id,
            "content": content,
            "modules": modules  # [추가됨] 백엔드에 어떤 기능을 쓸지 알려줌
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
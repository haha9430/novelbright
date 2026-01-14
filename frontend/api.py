#UI 코드 사이에 섞여 있던 requests 관련 코드

import requests
import streamlit as st

# 백엔드 주소 (나중에 배포할 때 여기만 바꾸면 됨)
BASE_URL = "http://127.0.0.1:8000"

def get_projects():
    """프로젝트 목록 가져오기"""
    try:
        res = requests.get(f"{BASE_URL}/projects")
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

def create_project(name, description):
    """새 프로젝트 생성"""
    try:
        res = requests.post(f"{BASE_URL}/projects", json={"name": name, "description": description})
        return res.status_code == 200
    except Exception as e:
        st.error(f"프로젝트 생성 실패: {e}")
        return False

def get_documents(project_id):
    """특정 프로젝트의 문서 목록 가져오기"""
    try:
        res = requests.get(f"{BASE_URL}/projects/{project_id}/documents")
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

def create_document(project_id, title):
    """새 문서 생성"""
    try:
        res = requests.post(f"{BASE_URL}/documents", json={"project_id": project_id, "title": title, "content": ""})
        return res.status_code == 200
    except Exception as e:
        st.error(f"문서 생성 실패: {e}")
        return False

def save_document(doc_id, title, content):
    """문서 저장"""
    try:
        payload = {"doc_id": doc_id, "title": title, "content": content}
        res = requests.post(f"{BASE_URL}/documents/save", json=payload)
        return res.status_code == 200
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

def analyze_text(doc_id, content):
    """AI 분석 요청 (Moneta)"""
    try:
        res = requests.post(f"{BASE_URL}/analyze/text", json={"doc_id": doc_id, "content": content})
        if res.status_code == 200:
            return res.json()
        else:
            st.error(f"분석 오류: {res.text}")
    except Exception as e:
        st.error(f"서버 연결 실패: {e}")
    return []
# app/service/clio_fact_checker_agent/router.py

import os
import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import Dict, Any

# 상대 경로 import 사용 (.service, .schemas)
from .schemas import ManuscriptInput
from .service import ManuscriptAnalyzer

router = APIRouter(prefix="/manuscript", tags=["Fact Checker"])

# 설정 파일 경로
# 주의: 실행 위치에 따라 경로가 달라질 수 있으므로 절대 경로 사용 권장
BASE_DIR = os.getcwd()
PLOT_DB_PATH = os.path.join(BASE_DIR, "app/data/plot.json") # 경로 확인 필요
CHARACTER_DB_PATH = os.path.join(BASE_DIR, "app/data/characters.json")

# Analyzer 인스턴스 (전역)
# 실제 프로덕션에서는 Depends를 이용한 의존성 주입을 권장하지만, 현재 구조 유지


@router.post("/analyze")
async def analyze_manuscript_file(
    title: str = Form(...),
    file: UploadFile = File(...)
):
    """
    [파일 업로드] 원고 분석 요청
    """
    analyzer = ManuscriptAnalyzer(setting_path=PLOT_DB_PATH, character_path=CHARACTER_DB_PATH)

    try:
        # 1. 파일 읽기 (Bytes -> String)
        content_bytes = await file.read()
        raw_content = content_bytes.decode("utf-8")

        # 2. [핵심] JSON 파싱 및 본문 추출
        # 사용자가 "JSON 내에서 소설의 키 값은 file"이라고 했으므로 이를 처리
        try:
            json_data = json.loads(raw_content)

            # JSON인 경우: 'file' 키가 있는지 확인
            if isinstance(json_data, dict) and "file" in json_data:
                real_text = json_data["file"] # 소설 본문만 추출
                print("✅ JSON 파일 감지: 'file' 키의 본문 내용을 추출했습니다.")
            else:
                # JSON이지만 'file' 키가 없거나 구조가 다르면 -> 일단 전체 사용 (혹은 에러 처리)
                real_text = raw_content
                print("⚠️ JSON 형식이지만 'file' 키를 찾을 수 없어 전체 내용을 사용합니다.")

        except json.JSONDecodeError:
            # JSON이 아님 (일반 txt 파일 등) -> 전체 내용 사용
            real_text = raw_content
            print("ℹ️ 일반 텍스트 파일로 처리합니다.")

        # 3. 분석 수행 (껍데기가 제거된 순수 본문만 전달)
        result = analyzer.analyze_manuscript(real_text)

        return {
            "title": title,
            "filename": file.filename,
            "analysis_result": result
        }

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일은 UTF-8 형식이어야 합니다.")
    except Exception as e:
        print(f"❌ 분석 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
import json
import os
from pathlib import Path
from typing import List, Dict, Any

# 라이브러리 임포트 (설치 여부 체크)
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
try:
    from docx import Document
except ImportError:
    Document = None


class FileProcessor:
    """
    파일(PDF, DOCX, TXT, JSON)을 읽어서 텍스트 데이터로 변환하는 처리기
    """

    @staticmethod
    def load_file_content(file_path: str) -> str:
        """
        파일 경로를 받아서 텍스트 내용을 추출해 반환합니다.
        """
        path = Path(file_path)
        if not path.exists():
            return f"[Error] 파일을 찾을 수 없습니다: {file_path}"

        ext = path.suffix.lower()

        try:
            # 1. JSON & TXT
            if ext == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # JSON은 보기 좋게 문자열로 변환
                return json.dumps(data, ensure_ascii=False, indent=2)

            elif ext == ".txt":
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except UnicodeDecodeError:
                    # 한글 윈도우(cp949) 대응
                    with open(path, "r", encoding="cp949") as f:
                        return f.read()

            # 2. PDF 파일
            elif ext == ".pdf":
                if not PdfReader:
                    return "[Error] pypdf 라이브러리가 설치되지 않았습니다."

                reader = PdfReader(path)
                full_text = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                return "\n".join(full_text)

            # 3. Word(DOCX) 파일
            elif ext in [".docx", ".doc"]:
                if not Document:
                    return "[Error] python-docx 라이브러리가 설치되지 않았습니다."

                doc = Document(path)
                return "\n".join([para.text for para in doc.paragraphs])

            # 4. HWP (미지원)
            elif ext == ".hwp":
                return "[Error] HWP 파일은 직접 지원하지 않습니다. PDF로 변환해서 테스트해주세요."

            else:
                return f"[Error] 지원하지 않는 확장자입니다: {ext}"

        except Exception as e:
            return f"[Error] 파일 읽기 중 예외 발생: {str(e)}"

    @staticmethod
    def parse_extracted_text(text_content: str, mode: str = "character") -> Any:
        """
        추출된 텍스트를 용도(mode)에 맞게 가공합니다.
        - mode='character': JSON 파싱 시도 -> 실패 시 통짜 텍스트로 설명 처리
        - mode='world': 그냥 텍스트 반환
        """
        # 1. JSON 파싱 시도 (형식이 갖춰진 파일인 경우)
        try:
            data = json.loads(text_content)
            # 만약 리스트나 딕셔너리면 그대로 반환
            if isinstance(data, (dict, list)):
                return data
        except json.JSONDecodeError:
            pass

        # 2. JSON이 아니면 그냥 줄글(Raw Text)로 처리
        if mode == "character":
            # 캐릭터인데 줄글이다? -> 이름은 '미정'으로 두고 내용을 설명에 넣음
            # (실제론 나중에 LLM이 내용을 보고 이름을 추출해야 함)
            return [{
                "name": "자동 감지 필요 (파일 내용)",
                "description": text_content[:500] + ("..." if len(text_content) > 500 else "")
            }]

        else:  # world 등
            return text_content
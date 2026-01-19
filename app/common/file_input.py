import json
import os
import tempfile
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
    def load_file_content(file_path) -> str:
        """
        파일 경로(str/Path) 또는 Streamlit UploadedFile을 받아서 텍스트 내용을 추출해 반환합니다.
        """
        tmp_path = None

        try:
            # 1) Streamlit UploadedFile 처리 (name + getvalue/read)
            if hasattr(file_path, "name") and (hasattr(file_path, "getvalue") or hasattr(file_path, "read")):
                filename = str(getattr(file_path, "name", "") or "")
                ext = Path(filename).suffix.lower()

                try:
                    data = file_path.getvalue() if hasattr(file_path, "getvalue") else file_path.read()
                except Exception as e:
                    return f"[Error] 업로드 파일 읽기 실패: {e}"

                if not isinstance(data, (bytes, bytearray)):
                    try:
                        data = bytes(data)
                    except Exception:
                        return "[Error] 업로드 파일 데이터 형식이 올바르지 않습니다."

                # txt/json이면 바로 디코딩해서 처리
                if ext in (".txt", ".json"):
                    try:
                        text_content = data.decode("utf-8")
                    except UnicodeDecodeError:
                        text_content = data.decode("cp949", errors="ignore")

                    if ext == ".json":
                        try:
                            obj = json.loads(text_content)
                            return json.dumps(obj, ensure_ascii=False, indent=2)
                        except Exception:
                            return text_content
                    return text_content

                # pdf/docx 등은 임시파일로 떨궈서 기존 경로 로직 태움
                try:
                    fd, tmp_path = tempfile.mkstemp(suffix=ext or ".bin")
                    os.close(fd)
                    with open(tmp_path, "wb") as f:
                        f.write(data)
                    file_path = tmp_path
                except Exception as e:
                    return f"[Error] 임시파일 생성 실패: {e}"

            # 2) 경로(str/Path) 처리
            path = Path(file_path)
            if not path.exists():
                return f"[Error] 파일을 찾을 수 없습니다: {file_path}"

            ext = path.suffix.lower()

            try:
                # 1. JSON & TXT
                if ext == ".json":
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return json.dumps(data, ensure_ascii=False, indent=2)

                elif ext == ".txt":
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            return f.read()
                    except UnicodeDecodeError:
                        with open(path, "r", encoding="cp949") as f:
                            return f.read()

                # 2. PDF 파일
                elif ext == ".pdf":
                    if not PdfReader:
                        return "[Error] pypdf 라이브러리가 설치되지 않았습니다."

                    reader = PdfReader(str(path))
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

                    doc = Document(str(path))
                    return "\n".join([para.text for para in doc.paragraphs])

                # 4. HWP (미지원)
                elif ext == ".hwp":
                    return "[Error] HWP 파일은 직접 지원하지 않습니다. PDF로 변환해서 테스트해주세요."

                else:
                    return f"[Error] 지원하지 않는 확장자입니다: {ext}"

            except Exception as e:
                return f"[Error] 파일 읽기 중 예외 발생: {str(e)}"

        finally:
            # 임시파일 정리
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    @staticmethod
    def parse_extracted_text(text_content: str, mode: str = "character") -> Any:
        """
        추출된 텍스트를 용도(mode)에 맞게 가공합니다.
        - mode='character': JSON 파싱 시도 -> 실패 시 통짜 텍스트로 설명 처리
        - mode='world': 그냥 텍스트 반환
        """
        try:
            data = json.loads(text_content)
            if isinstance(data, (dict, list)):
                return data
        except json.JSONDecodeError:
            pass

        if mode == "character":
            return [{
                "name": "자동 감지 필요 (파일 내용)",
                "description": text_content[:500] + ("..." if len(text_content) > 500 else "")
            }]
        else:
            return text_content

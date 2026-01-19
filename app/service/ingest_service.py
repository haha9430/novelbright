import os
import sys

# [수정] 폴더 구조에 맞게 경로 수정 (service 추가)
# [수정] 폴더 구조(app/service/...)에 맞게 경로를 보정합니다.
try:
    from app.service.characters import summarize_character_info
except ImportError:
    try:
        from service.characters import summarize_character_info
    except ImportError:
        def summarize_character_info(text):
            return {"status": "error", "message": "Character Module(app.service.characters)을 찾을 수 없습니다."}

try:
    # story_keeper_agent 앞에 service 경로를 추가해야 합니다.
    from app.service.story_keeper_agent.load_state.extracter import update_world_setting
except ImportError:
    try:
        from service.story_keeper_agent.load_state.extracter import update_world_setting
    except ImportError:
        def update_world_setting(text):
            return {"status": "error", "message": "World Module 경로를 확인하세요."}


class StoryIngestionService:
    """
    [역할]
    1. 파일 경로 처리 (Local Test용) -> process_file
    2. 텍스트 직접 처리 (Frontend API용) -> process_text  <-- 이게 핵심!
    """

    def process_file(self, file_path: str, upload_type: str) -> bool:
        """
        [로컬 파일용] 파일 경로를 받으면 텍스트를 뽑아서 process_text로 넘김
        """
        print(f"🔄 [IngestService] 파일 처리 시작: {file_path}")

        if not os.path.exists(file_path):
            print(f"❌ 파일 없음: {file_path}")
            return False

        # 텍스트 추출
        extracted_text = FileProcessor.load_file_content(file_path)
        if not extracted_text or extracted_text.startswith("[Error]"):
            print("❌ 텍스트 추출 실패")
            return False

        # 추출된 텍스트를 아래 process_text에게 넘김
        return self.process_text(extracted_text, upload_type)

    def process_text(self, text: str, upload_type: str) -> bool:
        """
        [API용] 프론트엔드에서 텍스트를 직접 받을 때 사용 (여기가 진짜 입구)
        """
        print(f"🔄 [IngestService] 텍스트 수신 (Type: {upload_type}, Length: {len(text)}자)")

        try:
            if upload_type == "character":
                return self._to_character_manager(text)

            elif upload_type == "world":
                return self._to_world_manager(text)

            else:
                print(f"⚠️ 지원하지 않는 타입: {upload_type}")
                return False

        except Exception as e:
            print(f"❌ 로직 처리 중 오류: {e}")
            return False

    # ---------------------------------------------------------
    # 내부 전달 함수들
    # ---------------------------------------------------------
    def _to_character_manager(self, text: str) -> bool:
        print("   👉 [To: Character Module] 캐릭터 저장 요청...")
        result = summarize_character_info(text)

        if result.get("status") == "success":
            names = result.get("names", [])
            print(f"      ✅ 캐릭터 저장 완료 ({len(names)}명): {', '.join(names)}")
            return True
        else:
            print(f"      ❌ 캐릭터 저장 실패: {result.get('message')}")
            return False

    def _to_world_manager(self, text: str) -> bool:
        print("   👉 [To: Plot Manager] 세계관 업데이트 요청...")
        result = update_world_setting(text)

        if result.get("status") == "success":
            print("      ✅ 세계관 업데이트 완료.")
            return True
        else:
            print(f"      ❌ 세계관 업데이트 실패: {result.get('message')}")
            return False
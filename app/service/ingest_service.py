import os

# 캐릭터 모듈
try:
    from app.service.characters import summarize_character_info
except ImportError:
    try:
        from service.characters import summarize_character_info
    except ImportError:
        def summarize_character_info(text):
            return {"status": "error", "message": "Character Module(app.service.characters)을 찾을 수 없습니다."}


# 세계관/플롯(PlotManager) 모듈
try:
    from app.service.story_keeper_agent.load_state.extracter import PlotManager
except ImportError:
    try:
        from service.story_keeper_agent.load_state.extracter import PlotManager
    except ImportError:
        PlotManager = None


_plot_manager_singleton = None


def _get_plot_manager():
    global _plot_manager_singleton
    if _plot_manager_singleton is not None:
        return _plot_manager_singleton

    if PlotManager is None:
        return None

    _plot_manager_singleton = PlotManager()
    return _plot_manager_singleton


def update_world_setting(text: str):
    """
    기존 코드가 찾던 update_world_setting 래퍼.
    실제 구현은 PlotManager.update_global_settings() 호출로 연결.
    """
    mgr = _get_plot_manager()
    if mgr is None:
        return {"status": "error", "message": "World Module 경로를 확인하세요."}

    try:
        return mgr.update_global_settings(text)
    except Exception as e:
        return {"status": "error", "message": f"world update failed: {e}"}


class StoryIngestionService:
    """
    1) 로컬 파일 경로 처리 -> process_file
    2) 프론트에서 받은 텍스트 처리 -> process_text
    """

    def process_file(self, file_path: str, upload_type: str) -> bool:
        """
        [로컬 파일용] 파일 경로를 받으면 텍스트를 뽑아서 process_text로 넘김
        """
        print(f"🔄 [IngestService] 파일 처리 시작: {file_path}")

        if not os.path.exists(file_path):
            print(f"❌ 파일 없음: {file_path}")
            return False

        # ⚠️ FileProcessor는 이 파일 안에 정의되어 있지 않음
        # 기존 프로젝트 구조대로 FileProcessor가 있는 곳에서 import 되어 있어야 함
        extracted_text = FileProcessor.load_file_content(file_path)  # noqa: F821
        if not extracted_text or extracted_text.startswith("[Error]"):
            print("❌ 텍스트 추출 실패")
            return False

        return self.process_text(extracted_text, upload_type)

    def process_text(self, text: str, upload_type: str) -> bool:
        """
        [API용] 프론트엔드에서 텍스트를 직접 받을 때 사용
        """
        upload_type = (upload_type or "").strip().lower()
        text = text or ""

        print(f"🔄 [IngestService] 텍스트 수신 (Type: {upload_type}, Length: {len(text)}자)")

        try:
            if upload_type == "character":
                return self._to_character_manager(text)

            # 프론트에서 world / worldview 둘 다 올 수 있음
            if upload_type in ("world", "worldview"):
                return self._to_world_manager(text)

            print(f"⚠️ 지원하지 않는 타입: {upload_type}")
            return False

        except Exception as e:
            print(f"❌ 로직 처리 중 오류: {e}")
            return False

    def _to_character_manager(self, text: str) -> bool:
        print("   👉 [To: Character Module] 캐릭터 저장 요청...")
        result = summarize_character_info(text)

        if result.get("status") == "success":
            names = result.get("names", [])
            print(f"      ✅ 캐릭터 저장 완료 ({len(names)}명): {', '.join(names)}")
            return True

        print(f"      ❌ 캐릭터 저장 실패: {result.get('message')}")
        return False

    def _to_world_manager(self, text: str) -> bool:
        print("   👉 [To: Plot Manager] 세계관 업데이트 요청...")
        result = update_world_setting(text)

        if result.get("status") == "success":
            print("      ✅ 세계관 업데이트 완료.")
            return True

        print(f"      ❌ 세계관 업데이트 실패: {result.get('message')}")
        return False

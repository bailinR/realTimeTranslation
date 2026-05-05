import asyncio
from pathlib import Path

from app.core.controller import AppController
from app.core.events import EventBus
from app.models import AppPaths, AppSettings, TranscriptResult
from app.store.database import Database


class DummySecrets:
    def get(self, name: str) -> str:
        return ""


def test_late_transcript_after_stop_does_not_restore_previous_translation(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    controller = AppController(
        settings=AppSettings(),
        paths=AppPaths(
            root=tmp_path,
            db_path=tmp_path / "app.db",
            settings_path=tmp_path / "settings.json",
            exports_dir=tmp_path / "exports",
            logs_dir=tmp_path / "logs",
        ),
        db=db,
        secrets=DummySecrets(),
        bus=EventBus(),
    )
    controller.session_id = 1
    controller._run_generation = 1
    controller.final_source_history = ["old source"]
    controller.final_translation_history = ["old translation"]

    async def run_test() -> None:
        translated = asyncio.Event()

        async def fake_translate(text: str, source_lang: str) -> str:
            translated.set()
            await asyncio.sleep(0)
            return "new translation"

        controller._translate = fake_translate  # type: ignore[method-assign]

        task = asyncio.create_task(
            controller._handle_transcript(
                TranscriptResult(
                    chunk_id=1,
                    start_ms=0,
                    end_ms=500,
                    text="hello",
                    source_lang="en",
                    provider="cloud",
                    is_final=True,
                )
            )
        )
        await translated.wait()
        controller.session_id = None
        controller._run_generation = 2
        await task

    asyncio.run(run_test())

    assert controller.segments_by_chunk == {}
    assert controller.final_source_history == ["old source"]
    assert controller.final_translation_history == ["old translation"]

    db.close()

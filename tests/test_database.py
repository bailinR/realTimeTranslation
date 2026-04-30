from datetime import datetime

from app.models import SubtitleSegment, SubtitleStatus
from app.store.database import Database


def test_upsert_and_export(tmp_path):
    db = Database(tmp_path / "app.db")
    session_id = db.create_session("steady", "auto")
    segment = SubtitleSegment(
        seq=0,
        session_id=session_id,
        chunk_id=1,
        started_at=datetime(2025, 1, 1, 12, 0, 0),
        ended_at=datetime(2025, 1, 1, 12, 0, 3),
        source_lang="en",
        source_text="hello world",
        translated_text="你好，世界",
        status=SubtitleStatus.FINAL,
        provider="cloud",
    )
    db.upsert_segment(segment)
    segments = db.list_segments(session_id)
    assert len(segments) == 1
    txt_path = tmp_path / "out.txt"
    srt_path = tmp_path / "out.srt"
    db.export_txt(session_id, txt_path)
    db.export_srt(session_id, srt_path)
    assert "hello world" in txt_path.read_text(encoding="utf-8")
    assert "你好，世界" in srt_path.read_text(encoding="utf-8")

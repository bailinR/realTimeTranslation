from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.models import SessionRecord, SubtitleSegment, SubtitleStatus


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    ended_at TEXT,
    mode TEXT NOT NULL,
    source_language TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    status TEXT NOT NULL,
    provider TEXT NOT NULL,
    UNIQUE(session_id, chunk_id),
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def create_session(self, mode: str, source_language: str) -> int:
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO sessions(created_at, mode, source_language) VALUES(?, ?, ?)",
            (now, mode, source_language),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def end_session(self, session_id: int) -> None:
        self.conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
            (datetime.now().isoformat(), session_id),
        )
        self.conn.commit()

    def upsert_segment(self, segment: SubtitleSegment) -> None:
        self.conn.execute(
            """
            INSERT INTO segments (
                session_id, chunk_id, started_at, ended_at, source_lang, source_text,
                translated_text, status, provider
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, chunk_id) DO UPDATE SET
                started_at = excluded.started_at,
                ended_at = excluded.ended_at,
                source_lang = excluded.source_lang,
                source_text = excluded.source_text,
                translated_text = excluded.translated_text,
                status = excluded.status,
                provider = excluded.provider
            """,
            (
                segment.session_id,
                segment.chunk_id,
                segment.started_at.isoformat(),
                segment.ended_at.isoformat(),
                segment.source_lang,
                segment.source_text,
                segment.translated_text,
                segment.status.value,
                segment.provider,
            ),
        )
        self.conn.commit()

    def list_sessions(self) -> list[SessionRecord]:
        rows = self.conn.execute(
            "SELECT session_id, created_at, ended_at, mode, source_language FROM sessions ORDER BY session_id DESC"
        ).fetchall()
        return [
            SessionRecord(
                session_id=row["session_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
                mode=row["mode"],
                source_language=row["source_language"],
            )
            for row in rows
        ]

    def list_segments(self, session_id: int) -> list[SubtitleSegment]:
        rows = self.conn.execute(
            """
            SELECT seq, session_id, chunk_id, started_at, ended_at, source_lang,
                   source_text, translated_text, status, provider
            FROM segments WHERE session_id = ?
            ORDER BY chunk_id ASC
            """,
            (session_id,),
        ).fetchall()
        return [
            SubtitleSegment(
                seq=row["seq"],
                session_id=row["session_id"],
                chunk_id=row["chunk_id"],
                started_at=datetime.fromisoformat(row["started_at"]),
                ended_at=datetime.fromisoformat(row["ended_at"]),
                source_lang=row["source_lang"],
                source_text=row["source_text"],
                translated_text=row["translated_text"],
                status=SubtitleStatus(row["status"]),
                provider=row["provider"],
            )
            for row in rows
        ]

    def export_txt(self, session_id: int, target: Path) -> None:
        lines: list[str] = []
        for segment in self.list_segments(session_id):
            stamp = segment.started_at.strftime("%H:%M:%S")
            lines.append(f"[{stamp}] ({segment.source_lang}) {segment.source_text}")
            lines.append(segment.translated_text)
            lines.append("")
        target.write_text("\n".join(lines), encoding="utf-8")

    def export_srt(self, session_id: int, target: Path) -> None:
        blocks: list[str] = []
        for index, segment in enumerate(self.list_segments(session_id), start=1):
            start = _to_srt_time(segment.started_at)
            end = _to_srt_time(segment.ended_at)
            blocks.append(f"{index}\n{start} --> {end}\n{segment.translated_text}\n")
        target.write_text("\n".join(blocks), encoding="utf-8")


def _to_srt_time(value: datetime) -> str:
    return value.strftime("%H:%M:%S,%f")[:-3]

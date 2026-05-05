"""Optional sqlite3 persistence for user-growth LLMwiki module records."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from noeticbraid_core.schemas._common import ensure_utc_datetime

from .models import ActivityLogRecord, LLMWikiSourceRecord, deterministic_json

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_records (
    record_id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    layer TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    relative_path TEXT,
    title TEXT,
    provenance_json TEXT NOT NULL,
    owner TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_log_records (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    layer TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    related_candidate_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    details_json TEXT NOT NULL,
    owner TEXT NOT NULL
);
"""


class LLMWikiSQLiteStore:
    """Narrow sqlite3 store for hashes, metadata, and activity records only.

    Raw private note content is intentionally not persisted here. The store uses
    SQLite transaction semantics and does not add a separate file lock; callers
    that need cross-process coordination can wrap this class at the application
    boundary (e.g. with ``filelock.ReadWriteLock``).
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def put_source_record(self, record: LLMWikiSourceRecord) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_records (
                    record_id, origin, content_hash, layer, ingested_at,
                    relative_path, title, provenance_json, owner
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.origin,
                    record.content_hash,
                    record.layer,
                    record.ingested_at.isoformat(),
                    record.relative_path,
                    record.title,
                    deterministic_json(record.provenance),
                    record.owner,
                ),
            )
            conn.commit()

    def get_source_record(self, record_id: str) -> Optional[LLMWikiSourceRecord]:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        return _row_to_source_record(row) if row else None

    def iter_source_records(self) -> Iterator[LLMWikiSourceRecord]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM source_records ORDER BY record_id").fetchall()
        for row in rows:
            yield _row_to_source_record(row)

    def append_activity(self, record: ActivityLogRecord) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO activity_log_records (
                    event_id, event_type, layer, source_refs_json,
                    related_candidate_refs_json, created_at, summary,
                    details_json, owner
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.event_type,
                    record.layer,
                    deterministic_json(record.source_refs),
                    deterministic_json(record.related_candidate_refs),
                    record.created_at.isoformat(),
                    record.summary,
                    deterministic_json(record.details),
                    record.owner,
                ),
            )
            conn.commit()

    def iter_activity(self) -> Iterator[ActivityLogRecord]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM activity_log_records ORDER BY created_at, event_id").fetchall()
        for row in rows:
            yield _row_to_activity_record(row)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


def _parse_dt(value: str) -> datetime:
    return ensure_utc_datetime(datetime.fromisoformat(value))


def _row_to_source_record(row: sqlite3.Row) -> LLMWikiSourceRecord:
    provenance = json.loads(row["provenance_json"])
    if not isinstance(provenance, dict):
        provenance = {}
    return LLMWikiSourceRecord(
        record_id=row["record_id"],
        origin=row["origin"],
        content_hash=row["content_hash"],
        layer=row["layer"],
        ingested_at=_parse_dt(row["ingested_at"]),
        relative_path=row["relative_path"],
        title=row["title"],
        provenance={str(key): str(value) for key, value in provenance.items()},
        owner=row["owner"],
    )


def _row_to_activity_record(row: sqlite3.Row) -> ActivityLogRecord:
    return ActivityLogRecord(
        event_id=row["event_id"],
        event_type=row["event_type"],
        layer=row["layer"],
        source_refs=[str(item) for item in json.loads(row["source_refs_json"])],
        related_candidate_refs=[str(item) for item in json.loads(row["related_candidate_refs_json"])],
        created_at=_parse_dt(row["created_at"]),
        summary=row["summary"],
        details={str(key): str(value) for key, value in json.loads(row["details_json"]).items()},
        owner=row["owner"],
    )

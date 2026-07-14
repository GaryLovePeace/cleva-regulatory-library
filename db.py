from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import SETTINGS

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS search_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT NOT NULL,
  jurisdictions_json TEXT NOT NULL,
  topic TEXT,
  provider TEXT,
  search_mode TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  search_run_id INTEGER,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  snippet TEXT,
  published_date TEXT,
  source_name TEXT,
  source_domain TEXT,
  source_level TEXT,
  source_type TEXT,
  jurisdiction_group TEXT,
  is_official INTEGER NOT NULL DEFAULT 0,
  is_curated INTEGER NOT NULL DEFAULT 0,
  verification_required INTEGER NOT NULL DEFAULT 1,
  content_hash TEXT,
  extracted_text TEXT,
  ai_json TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  approved_record_type TEXT,
  reviewer TEXT,
  review_note TEXT,
  created_at TEXT NOT NULL,
  reviewed_at TEXT,
  FOREIGN KEY(search_run_id) REFERENCES search_runs(id)
);

CREATE TABLE IF NOT EXISTS regulations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER,
  original_title TEXT NOT NULL,
  chinese_title TEXT,
  regulation_number TEXT,
  jurisdiction TEXT,
  country TEXT,
  state_province TEXT,
  authority TEXT,
  document_type TEXT,
  legal_status TEXT,
  publication_date TEXT,
  entry_into_force_date TEXT,
  application_date TEXT,
  compliance_deadline TEXT,
  topics_json TEXT,
  business_lines_json TEXT,
  relevance_level TEXT,
  summary_cn TEXT,
  cleva_impact TEXT,
  official_url TEXT NOT NULL,
  discovery_url TEXT,
  pdf_url TEXT,
  source_name TEXT,
  source_level TEXT,
  content_hash TEXT,
  version_label TEXT NOT NULL DEFAULT '1',
  last_verified_date TEXT,
  reviewer TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES candidates(id)
);

CREATE TABLE IF NOT EXISTS intelligence_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER,
  original_title TEXT NOT NULL,
  chinese_title TEXT,
  jurisdiction TEXT,
  publication_date TEXT,
  topics_json TEXT,
  business_lines_json TEXT,
  relevance_level TEXT,
  summary_cn TEXT,
  cleva_impact TEXT,
  source_url TEXT NOT NULL UNIQUE,
  source_name TEXT,
  source_type TEXT,
  source_level TEXT,
  related_official_url TEXT,
  last_verified_date TEXT,
  reviewer TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES candidates(id)
);

CREATE TABLE IF NOT EXISTS review_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  reviewer TEXT,
  note TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES candidates(id)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path: Path = SETTINGS.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Safe migrations for users who already ran version 0.1.
        _ensure_column(conn, "search_runs", "search_mode", "TEXT")
        _ensure_column(conn, "candidates", "source_type", "TEXT")
        _ensure_column(conn, "candidates", "is_curated", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "candidates", "verification_required", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "candidates", "approved_record_type", "TEXT")
        _ensure_column(conn, "regulations", "discovery_url", "TEXT")


def create_search_run(
    query: str,
    jurisdictions: list[str],
    topic: str,
    provider: str,
    search_mode: str = "quick",
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO search_runs(query,jurisdictions_json,topic,provider,search_mode,created_at)
            VALUES(?,?,?,?,?,?)""",
            (query, json.dumps(jurisdictions, ensure_ascii=False), topic, provider, search_mode, utc_now()),
        )
        return int(cur.lastrowid)


def upsert_candidate(search_run_id: int, item: dict[str, Any]) -> int:
    ai_json = json.dumps(item.get("ai_data") or {}, ensure_ascii=False)
    with connect() as conn:
        existing = conn.execute("SELECT id FROM candidates WHERE url=?", (item["url"],)).fetchone()
        values = (
            search_run_id,
            item.get("title") or item["url"],
            item["url"],
            item.get("snippet"),
            item.get("published_date"),
            item.get("source_name"),
            item.get("source_domain"),
            item.get("source_level"),
            item.get("source_type"),
            item.get("jurisdiction_group"),
            1 if item.get("is_official") else 0,
            1 if item.get("is_curated") else 0,
            1 if item.get("verification_required", True) else 0,
            item.get("content_hash"),
            item.get("extracted_text"),
            ai_json,
        )
        if existing:
            conn.execute(
                """UPDATE candidates SET search_run_id=?,title=?,url=?,snippet=?,published_date=?,source_name=?,
                source_domain=?,source_level=?,source_type=?,jurisdiction_group=?,is_official=?,is_curated=?,
                verification_required=?,content_hash=?,extracted_text=?,ai_json=?,status='pending',
                approved_record_type=NULL,reviewer=NULL,review_note=NULL,reviewed_at=NULL WHERE id=?""",
                values + (int(existing["id"]),),
            )
            return int(existing["id"])
        cur = conn.execute(
            """INSERT INTO candidates(search_run_id,title,url,snippet,published_date,source_name,
            source_domain,source_level,source_type,jurisdiction_group,is_official,is_curated,
            verification_required,content_hash,extracted_text,ai_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values + (utc_now(),),
        )
        return int(cur.lastrowid)


def list_candidates(status: str = "pending", limit: int = 300) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM candidates WHERE status=? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()


def get_candidate(candidate_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()


def _record_review(
    conn: sqlite3.Connection,
    candidate_id: int,
    action: str,
    reviewer: str,
    note: str,
    status: str,
    approved_record_type: str | None = None,
) -> None:
    conn.execute(
        """UPDATE candidates SET status=?,approved_record_type=?,reviewer=?,review_note=?,reviewed_at=?
        WHERE id=?""",
        (status, approved_record_type, reviewer, note, utc_now(), candidate_id),
    )
    conn.execute(
        "INSERT INTO review_history(candidate_id,action,reviewer,note,created_at) VALUES(?,?,?,?,?)",
        (candidate_id, action, reviewer, note, utc_now()),
    )


def review_candidate(candidate_id: int, action: str, reviewer: str, note: str = "") -> None:
    status_map = {"reject": "rejected", "duplicate": "duplicate"}
    if action not in status_map:
        raise ValueError(f"Unsupported review action: {action}")
    with connect() as conn:
        _record_review(conn, candidate_id, action, reviewer, note, status_map[action])


def promote_candidate_to_regulation(
    candidate_id: int,
    reviewer: str,
    *,
    official_url: str | None = None,
    note: str = "",
    overrides: dict[str, Any] | None = None,
) -> int:
    candidate = get_candidate(candidate_id)
    if candidate is None:
        raise ValueError("Candidate not found")
    ai = json.loads(candidate["ai_json"] or "{}")
    data = {**ai, **(overrides or {})}
    verified_url = (official_url or data.get("official_url") or candidate["url"]).strip()
    if not candidate["is_official"] and verified_url == candidate["url"]:
        raise ValueError("非官方来源不能直接作为正式法规入库，请填写已人工核验的官方法规链接。")

    now = utc_now()
    fields = {
        "candidate_id": candidate_id,
        "original_title": data.get("original_title") or candidate["title"],
        "chinese_title": data.get("chinese_title"),
        "regulation_number": data.get("regulation_number"),
        "jurisdiction": data.get("jurisdiction") or candidate["jurisdiction_group"],
        "country": data.get("country"),
        "state_province": data.get("state_province"),
        "authority": data.get("authority"),
        "document_type": data.get("document_type"),
        "legal_status": data.get("legal_status"),
        "publication_date": data.get("publication_date") or candidate["published_date"],
        "entry_into_force_date": data.get("entry_into_force_date"),
        "application_date": data.get("application_date"),
        "compliance_deadline": data.get("compliance_deadline"),
        "topics_json": json.dumps(data.get("topics") or [], ensure_ascii=False),
        "business_lines_json": json.dumps(data.get("business_lines") or [], ensure_ascii=False),
        "relevance_level": data.get("relevance_level") or "Needs review",
        "summary_cn": data.get("summary_cn"),
        "cleva_impact": data.get("cleva_impact"),
        "official_url": verified_url,
        "discovery_url": candidate["url"] if verified_url != candidate["url"] else None,
        "pdf_url": data.get("pdf_url"),
        "source_name": candidate["source_name"] if candidate["is_official"] else "Manual official verification",
        "source_level": candidate["source_level"] if candidate["is_official"] else "A/B - verify manually",
        "content_hash": candidate["content_hash"],
        "last_verified_date": now[:10],
        "reviewer": reviewer,
        "updated_at": now,
    }

    with connect() as conn:
        existing = conn.execute("SELECT id FROM regulations WHERE official_url=?", (verified_url,)).fetchone()
        if existing:
            assignments = ",".join(f"{key}=?" for key in fields)
            conn.execute(
                f"UPDATE regulations SET {assignments} WHERE id=?",
                tuple(fields.values()) + (int(existing["id"]),),
            )
            record_id = int(existing["id"])
        else:
            insert_fields = {**fields, "created_at": now}
            columns = ",".join(insert_fields)
            placeholders = ",".join("?" for _ in insert_fields)
            cur = conn.execute(
                f"INSERT INTO regulations({columns}) VALUES({placeholders})",
                tuple(insert_fields.values()),
            )
            record_id = int(cur.lastrowid)
        _record_review(conn, candidate_id, "approve_regulation", reviewer, note, "approved", "regulation")
    return record_id


def promote_candidate_to_intelligence(
    candidate_id: int,
    reviewer: str,
    *,
    related_official_url: str = "",
    note: str = "",
    overrides: dict[str, Any] | None = None,
) -> int:
    candidate = get_candidate(candidate_id)
    if candidate is None:
        raise ValueError("Candidate not found")
    ai = json.loads(candidate["ai_json"] or "{}")
    data = {**ai, **(overrides or {})}
    now = utc_now()
    fields = {
        "candidate_id": candidate_id,
        "original_title": data.get("original_title") or candidate["title"],
        "chinese_title": data.get("chinese_title"),
        "jurisdiction": data.get("jurisdiction") or candidate["jurisdiction_group"],
        "publication_date": data.get("publication_date") or candidate["published_date"],
        "topics_json": json.dumps(data.get("topics") or [], ensure_ascii=False),
        "business_lines_json": json.dumps(data.get("business_lines") or [], ensure_ascii=False),
        "relevance_level": data.get("relevance_level") or "Unclear",
        "summary_cn": data.get("summary_cn") or candidate["snippet"],
        "cleva_impact": data.get("cleva_impact"),
        "source_url": candidate["url"],
        "source_name": candidate["source_name"],
        "source_type": candidate["source_type"],
        "source_level": candidate["source_level"],
        "related_official_url": related_official_url.strip() or data.get("related_official_url"),
        "last_verified_date": now[:10],
        "reviewer": reviewer,
        "updated_at": now,
    }
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM intelligence_records WHERE source_url=?", (candidate["url"],)
        ).fetchone()
        if existing:
            assignments = ",".join(f"{key}=?" for key in fields)
            conn.execute(
                f"UPDATE intelligence_records SET {assignments} WHERE id=?",
                tuple(fields.values()) + (int(existing["id"]),),
            )
            record_id = int(existing["id"])
        else:
            insert_fields = {**fields, "created_at": now}
            columns = ",".join(insert_fields)
            placeholders = ",".join("?" for _ in insert_fields)
            cur = conn.execute(
                f"INSERT INTO intelligence_records({columns}) VALUES({placeholders})",
                tuple(insert_fields.values()),
            )
            record_id = int(cur.lastrowid)
        _record_review(conn, candidate_id, "approve_intelligence", reviewer, note, "approved", "intelligence")
    return record_id


# Backwards-compatible function used by version 0.1 callers.
def promote_candidate(candidate_id: int, reviewer: str, overrides: dict[str, Any] | None = None) -> int:
    return promote_candidate_to_regulation(candidate_id, reviewer, overrides=overrides)


def list_regulations(search: str = "", limit: int = 500) -> list[sqlite3.Row]:
    with connect() as conn:
        if search.strip():
            pattern = f"%{search.strip()}%"
            return conn.execute(
                """SELECT * FROM regulations WHERE original_title LIKE ? OR chinese_title LIKE ?
                OR regulation_number LIKE ? OR summary_cn LIKE ? OR cleva_impact LIKE ?
                ORDER BY updated_at DESC LIMIT ?""",
                (pattern, pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return conn.execute("SELECT * FROM regulations ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()


def list_intelligence(search: str = "", limit: int = 500) -> list[sqlite3.Row]:
    with connect() as conn:
        if search.strip():
            pattern = f"%{search.strip()}%"
            return conn.execute(
                """SELECT * FROM intelligence_records WHERE original_title LIKE ? OR chinese_title LIKE ?
                OR summary_cn LIKE ? OR cleva_impact LIKE ? OR source_name LIKE ?
                ORDER BY updated_at DESC LIMIT ?""",
                (pattern, pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM intelligence_records ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()


def get_regulation(regulation_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM regulations WHERE id=?", (regulation_id,)).fetchone()

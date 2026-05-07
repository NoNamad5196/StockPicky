# -*- coding: utf-8 -*-
import sqlite3
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

_conn: Optional[sqlite3.Connection] = None


def _get_conn(db_path: str = "stockpicky.db") -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.commit()
    return _conn


def init_db(db_path: str = "stockpicky.db") -> None:
    global _conn
    _conn = None
    conn = _get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker   TEXT NOT NULL COLLATE NOCASE,
            market   TEXT NOT NULL DEFAULT 'US',
            added_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(ticker COLLATE NOCASE)
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            title       TEXT,
            source      TEXT,
            url         TEXT,
            raw_summary TEXT,
            hash        TEXT UNIQUE,
            collected_at TEXT,
            is_sent     INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS analysis (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id            INTEGER NOT NULL,
            sentiment           TEXT,
            market_impact_score INTEGER,
            urgency_score       INTEGER,
            credibility_score   INTEGER,
            alert_level         INTEGER,
            should_alert        INTEGER,
            headline_mood       TEXT,
            summary             TEXT,
            reason_json         TEXT,
            risk_note           TEXT,
            created_at          TEXT
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id        INTEGER NOT NULL,
            message_preview TEXT,
            sent_at         TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            report_type TEXT,
            content     TEXT,
            sent_at     TEXT
        );
    """)
    conn.commit()
    logger.info("DB 초기화 완료: %s", db_path)


# ── watchlist CRUD ────────────────────────────────────────────────────────────

def add_ticker(ticker: str, market: str = "US") -> bool:
    ticker = ticker.upper()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, market, added_at) VALUES (?, ?, ?)",
            (ticker, market.upper(), datetime.now(KST).isoformat()),
        )
        conn.commit()
        logger.info("watchlist 추가: %s (%s)", ticker, market)
        return True
    except sqlite3.IntegrityError:
        logger.debug("이미 있는 종목: %s", ticker)
        return False


def remove_ticker(ticker: str) -> bool:
    ticker = ticker.upper()
    conn = _get_conn()
    cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
    conn.commit()
    if cur.rowcount > 0:
        logger.info("watchlist 삭제: %s", ticker)
        return True
    return False


def pause_ticker(ticker: str) -> bool:
    ticker = ticker.upper()
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE watchlist SET is_active = 0 WHERE ticker = ? AND is_active = 1",
        (ticker,),
    )
    conn.commit()
    return cur.rowcount > 0


def resume_ticker(ticker: str) -> bool:
    ticker = ticker.upper()
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE watchlist SET is_active = 1 WHERE ticker = ? AND is_active = 0",
        (ticker,),
    )
    conn.commit()
    return cur.rowcount > 0


def get_active_tickers() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ticker, market FROM watchlist WHERE is_active = 1 ORDER BY added_at"
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_tickers() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ticker, market, is_active, added_at FROM watchlist ORDER BY added_at"
    ).fetchall()
    return [dict(r) for r in rows]


# ── events ────────────────────────────────────────────────────────────────────

def _make_hash(ticker: str, title: str, source: str) -> str:
    raw = f"{ticker}:{title}:{source}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def save_event(event) -> Optional[int]:
    """StockEvent를 저장. 중복이면 None 반환."""
    h = _make_hash(event.ticker, event.title, event.source)
    conn = _get_conn()
    cur = conn.execute(
        """INSERT OR IGNORE INTO events
           (ticker, event_type, title, source, url, raw_summary, hash, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event.ticker,
            event.event_type,
            event.title,
            event.source,
            event.url,
            event.summary,
            h,
            event.collected_at,
        ),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    event_id = cur.lastrowid
    conn.execute(
        """INSERT INTO analysis
           (event_id, sentiment, market_impact_score, urgency_score,
            credibility_score, alert_level, should_alert,
            headline_mood, summary, reason_json, risk_note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event_id,
            event.sentiment,
            event.market_impact_score,
            event.urgency_score,
            event.credibility_score,
            event.alert_level,
            int(event.should_alert),
            event.headline_mood,
            event.summary,
            json.dumps(event.reason, ensure_ascii=False),
            event.risk_note,
            datetime.now(KST).isoformat(),
        ),
    )
    conn.commit()
    return event_id


def mark_sent(event_id: int, message_preview: str) -> None:
    conn = _get_conn()
    conn.execute("UPDATE events SET is_sent = 1 WHERE id = ?", (event_id,))
    conn.execute(
        "INSERT INTO alerts (event_id, message_preview, sent_at) VALUES (?, ?, ?)",
        (event_id, message_preview[:200], datetime.now(KST).isoformat()),
    )
    conn.commit()


def get_today_events(min_level: int = 3) -> list[dict]:
    today = datetime.now(KST).strftime("%Y-%m-%d")
    conn = _get_conn()
    rows = conn.execute(
        """SELECT e.ticker, e.event_type, e.title, e.source,
                  a.sentiment, a.alert_level, a.headline_mood, a.summary
           FROM events e
           JOIN analysis a ON a.event_id = e.id
           WHERE e.collected_at LIKE ?
             AND a.alert_level >= ?
           ORDER BY a.alert_level DESC, e.collected_at DESC""",
        (f"{today}%", min_level),
    ).fetchall()
    return [dict(r) for r in rows]


def save_daily_report(report_date: str, report_type: str, content: str) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO daily_reports (report_date, report_type, content, sent_at) VALUES (?, ?, ?, ?)",
        (report_date, report_type, content, datetime.now(KST).isoformat()),
    )
    conn.commit()

"""SQLite-backed history of runs and per-scenario results.

Lets you query across runs: 'how did scenario 014 score over the last 20 runs',
'what was the aggregate score before and after the prompt change tagged X', etc.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from .schema import RunSummary

DB_PATH = Path(__file__).parent.parent / "runs" / "history.sqlite"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT,
            git_sha TEXT,
            model TEXT,
            prompt_version TEXT,
            tag TEXT,
            aggregate_score REAL,
            pass_rate REAL,
            total_cost_usd REAL,
            total_duration_ms INTEGER
        );
        CREATE TABLE IF NOT EXISTS scenario_results (
            run_id TEXT,
            scenario_id TEXT,
            weighted_score REAL,
            passed INTEGER,
            cost_usd REAL,
            duration_ms INTEGER,
            PRIMARY KEY (run_id, scenario_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        """
    )
    conn.commit()
    return conn


def store_run(summary: RunSummary) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            summary.run_id,
            summary.started_at,
            summary.git_sha,
            summary.model,
            summary.prompt_version,
            summary.tag,
            summary.aggregate_score,
            summary.pass_rate,
            summary.total_cost_usd,
            summary.total_duration_ms,
        ),
    )
    for r in summary.scenario_results:
        conn.execute(
            "INSERT OR REPLACE INTO scenario_results VALUES (?, ?, ?, ?, ?, ?)",
            (
                summary.run_id,
                r.scenario_id,
                r.weighted_score,
                int(r.passed),
                r.cost_usd,
                r.duration_ms,
            ),
        )
    conn.commit()
    conn.close()


def get_previous_run_id(exclude_run_id: str) -> Optional[str]:
    """Get the run_id of the most recent run other than the given one."""
    conn = _conn()
    row = conn.execute(
        "SELECT run_id FROM runs WHERE run_id != ? "
        "ORDER BY started_at DESC LIMIT 1",
        (exclude_run_id,),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_run_summary(run_id: str) -> Optional[dict]:
    """Get the run row (without scenario_results) as a dict."""
    conn = _conn()
    cursor = conn.execute(
        "SELECT run_id, started_at, git_sha, model, prompt_version, tag, "
        "aggregate_score, pass_rate, total_cost_usd, total_duration_ms "
        "FROM runs WHERE run_id = ?",
        (run_id,),
    )
    cols = [c[0] for c in cursor.description]
    row = cursor.fetchone()
    conn.close()
    return dict(zip(cols, row)) if row else None


def get_scenario_results(run_id: str) -> list[dict]:
    """Get all scenario results for a run as list of dicts."""
    conn = _conn()
    cursor = conn.execute(
        "SELECT scenario_id, weighted_score, passed, cost_usd, duration_ms "
        "FROM scenario_results WHERE run_id = ?",
        (run_id,),
    )
    cols = [c[0] for c in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def scenario_history(scenario_id: str, limit: int = 20) -> list[dict]:
    """Get the history of one scenario's scores across recent runs."""
    conn = _conn()
    cursor = conn.execute(
        """
        SELECT r.run_id, r.started_at, r.prompt_version, r.tag,
               sr.weighted_score, sr.passed
        FROM scenario_results sr
        JOIN runs r ON sr.run_id = r.run_id
        WHERE sr.scenario_id = ?
        ORDER BY r.started_at DESC
        LIMIT ?
        """,
        (scenario_id, limit),
    )
    cols = [c[0] for c in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(cols, r)) for r in rows]

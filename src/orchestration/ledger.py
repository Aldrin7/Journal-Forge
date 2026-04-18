"""
PaperForge — SQLite Progress Ledger
Tracks file processing state for session resumption.

Schema per spec:
  progress: file_id TEXT, step TEXT, last_row INTEGER, ts TIMESTAMP
  runs:     run_id → journal, format, status, summary
  checkpoints: run_id, step, state_json (also written to filesystem)

All writes use SQLite WAL mode for concurrent access safety.
"""
import sqlite3
import datetime
import pathlib
import json
from typing import Optional, List, Dict, Any

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "ledger.sqlite"


def get_connection(db_path: Optional[pathlib.Path] = None) -> sqlite3.Connection:
    """Create WAL-mode autocommit connection with busy-timeout."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), isolation_level=None)  # autocommit
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA busy_timeout=5000;")
    _ensure_tables(con)
    return con


def _ensure_tables(con: sqlite3.Connection) -> None:
    """Create tables if they don't exist (idempotent)."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            run_id    TEXT,
            file_id   TEXT,
            step      TEXT,
            status    TEXT DEFAULT 'pending',
            last_row  INTEGER,
            metadata  TEXT,
            ts        TEXT,
            PRIMARY KEY (run_id, file_id, step)
        );
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id     TEXT PRIMARY KEY,
            file_id    TEXT,
            journal    TEXT,
            format     TEXT,
            started    TEXT,
            completed  TEXT,
            status     TEXT DEFAULT 'running',
            summary    TEXT
        );
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id        TEXT,
            step          TEXT,
            state_json    TEXT,
            ts            TEXT
        );
    """)
    # Index for fast resume queries
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_progress_run
        ON progress(run_id, file_id, status);
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_checkpoints_run
        ON checkpoints(run_id, checkpoint_id DESC);
    """)


class Ledger:
    """SQLite-backed progress ledger for pipeline state tracking."""

    def __init__(self, db_path: Optional[pathlib.Path] = None):
        self.con = get_connection(db_path)

    # ── Run management ──────────────────────────────────────────────

    def create_run(self, run_id: str, file_id: str, journal: str,
                   fmt: str) -> None:
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        self.con.execute(
            "INSERT OR REPLACE INTO runs (run_id,file_id,journal,format,started,status) "
            "VALUES (?,?,?,?,?,?)",
            (run_id, file_id, journal, fmt, ts, "running"))

    def complete_run(self, run_id: str, summary: Optional[str] = None) -> None:
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        self.con.execute(
            "UPDATE runs SET completed=?, status='completed', summary=? WHERE run_id=?",
            (ts, summary, run_id))

    def fail_run(self, run_id: str, error: str) -> None:
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        self.con.execute(
            "UPDATE runs SET completed=?, status='failed', summary=? WHERE run_id=?",
            (ts, error, run_id))

    # ── Step tracking ───────────────────────────────────────────────

    def log_step(self, run_id: str, file_id: str, step: str,
                 status: str = "completed",
                 last_row: Optional[int] = None,
                 metadata: Optional[dict] = None) -> None:
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        meta_json = json.dumps(metadata) if metadata else None
        self.con.execute(
            "INSERT OR REPLACE INTO progress "
            "(run_id,file_id,step,status,last_row,metadata,ts) VALUES (?,?,?,?,?,?,?)",
            (run_id, file_id, step, status, last_row, meta_json, ts))

    def get_step(self, run_id: str, file_id: str, step: str) -> Optional[Dict]:
        cur = self.con.execute(
            "SELECT run_id,file_id,step,status,last_row,metadata,ts FROM progress "
            "WHERE run_id=? AND file_id=? AND step=?",
            (run_id, file_id, step))
        row = cur.fetchone()
        if row:
            return {
                "run_id": row[0], "file_id": row[1], "step": row[2],
                "status": row[3], "last_row": row[4],
                "metadata": json.loads(row[5]) if row[5] else None,
                "ts": row[6]
            }
        return None

    def get_run_steps(self, run_id: str, file_id: str) -> List[Dict]:
        cur = self.con.execute(
            "SELECT run_id,file_id,step,status,last_row,metadata,ts FROM progress "
            "WHERE run_id=? AND file_id=? ORDER BY ts",
            (run_id, file_id))
        return [{
            "run_id": r[0], "file_id": r[1], "step": r[2],
            "status": r[3], "last_row": r[4],
            "metadata": json.loads(r[5]) if r[5] else None,
            "ts": r[6]
        } for r in cur.fetchall()]

    def get_completed_steps(self, run_id: str, file_id: str) -> List[str]:
        cur = self.con.execute(
            "SELECT step FROM progress WHERE run_id=? AND file_id=? AND status='completed'",
            (run_id, file_id))
        return [r[0] for r in cur.fetchall()]

    def is_step_done(self, run_id: str, file_id: str, step: str) -> bool:
        cur = self.con.execute(
            "SELECT status FROM progress WHERE run_id=? AND file_id=? AND step=? AND status='completed'",
            (run_id, file_id, step))
        return cur.fetchone() is not None

    # ── Checkpointing (SQLite + filesystem) ─────────────────────────

    def save_checkpoint(self, run_id: str, step: str, state: dict,
                        checkpoint_dir: Optional[pathlib.Path] = None) -> int:
        """
        Save checkpoint to both SQLite and filesystem.
        The filesystem copy enables manual inspection and fastio upload.
        """
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        state_json = json.dumps(state, default=str)

        # SQLite
        cur = self.con.execute(
            "INSERT INTO checkpoints (run_id,step,state_json,ts) VALUES (?,?,?,?)",
            (run_id, step, state_json, ts))
        checkpoint_id = cur.lastrowid

        # Filesystem: checkpoints/<run_id>/<step>.json
        if checkpoint_dir is None:
            checkpoint_dir = pathlib.Path("checkpoints")
        fs_path = checkpoint_dir / run_id / f"{step}.json"
        fs_path.parent.mkdir(parents=True, exist_ok=True)
        fs_path.write_text(state_json)

        # Also write a latest.json for quick resume
        latest_path = checkpoint_dir / run_id / "latest.json"
        latest_path.write_text(json.dumps({
            "checkpoint_id": checkpoint_id,
            "step": step,
            "state": state,
            "ts": ts,
        }, indent=2, default=str))

        return checkpoint_id

    def load_checkpoint(self, checkpoint_id: int) -> Optional[Dict]:
        cur = self.con.execute(
            "SELECT state_json FROM checkpoints WHERE checkpoint_id=?",
            (checkpoint_id,))
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def get_latest_checkpoint(self, run_id: str) -> Optional[Dict]:
        cur = self.con.execute(
            "SELECT checkpoint_id,step,state_json,ts FROM checkpoints "
            "WHERE run_id=? ORDER BY checkpoint_id DESC LIMIT 1",
            (run_id,))
        row = cur.fetchone()
        if row:
            return {
                "checkpoint_id": row[0], "step": row[1],
                "state": json.loads(row[2]), "ts": row[3]
            }
        return None

    # ── Resume logic ────────────────────────────────────────────────

    def get_resumable_runs(self) -> List[Dict]:
        cur = self.con.execute(
            "SELECT run_id,file_id,journal,format,started FROM runs WHERE status='running'")
        return [{
            "run_id": r[0], "file_id": r[1], "journal": r[2],
            "format": r[3], "started": r[4]
        } for r in cur.fetchall()]

    def get_last_completed_step(self, run_id: str, file_id: str) -> Optional[str]:
        cur = self.con.execute(
            "SELECT step FROM progress WHERE run_id=? AND file_id=? AND status='completed' "
            "ORDER BY ts DESC LIMIT 1",
            (run_id, file_id))
        row = cur.fetchone()
        return row[0] if row else None

    def get_last_row(self, run_id: str, file_id: str, step: str) -> Optional[int]:
        """Get the last processed row for incremental resume."""
        cur = self.con.execute(
            "SELECT last_row FROM progress WHERE run_id=? AND file_id=? AND step=?",
            (run_id, file_id, step))
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    def close(self):
        self.con.close()

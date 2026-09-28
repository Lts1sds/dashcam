import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    name TEXT,
    status TEXT DEFAULT 'running',
    started_at REAL,
    ended_at REAL
);
CREATE TABLE IF NOT EXISTS spans (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    idx INTEGER,
    provider TEXT,
    kind TEXT,
    model TEXT,
    started_at REAL,
    ended_at REAL,
    request TEXT,
    response TEXT,
    error TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cost REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_spans_trace ON spans(trace_id, idx);
CREATE INDEX IF NOT EXISTS ix_traces_started ON traces(started_at);
"""

RUNNING_IDLE_SECONDS = 300.0


def default_db_path():
    override = os.environ.get("DASHCAM_DB")
    if override:
        return override
    return str(Path.home() / ".dashcam" / "traces.db")


class Store:
    def __init__(self, path=None):
        self.path = path or default_db_path()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    @staticmethod
    def new_id():
        return uuid.uuid4().hex[:12]

    def start_trace(self, name=None, started_at=None):
        tid = self.new_id()
        with self._lock:
            self._conn.execute(
                "INSERT INTO traces (id, name, status, started_at) VALUES (?,?,?,?)",
                (tid, name, "running", started_at or time.time()))
            self._conn.commit()
        return tid

    def rename_trace(self, tid, name):
        with self._lock:
            self._conn.execute(
                "UPDATE traces SET name=? WHERE id=? AND (name IS NULL OR name='')",
                (name, tid))
            self._conn.commit()

    def end_trace(self, tid, status="ok"):
        with self._lock:
            self._conn.execute(
                "UPDATE traces SET ended_at=?, status=? WHERE id=?",
                (time.time(), status, tid))
            self._conn.commit()

    def record_span(self, trace_id, idx, provider, kind, model,
                    started_at, ended_at, request, response, error,
                    prompt_tokens, completion_tokens, cost):
        sid = self.new_id()
        with self._lock:
            self._conn.execute(
                "INSERT INTO spans (id, trace_id, idx, provider, kind, model,"
                " started_at, ended_at, request, response, error,"
                " prompt_tokens, completion_tokens, cost)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, trace_id, idx, provider, kind, model,
                 started_at, ended_at,
                 _dumps(request), _dumps(response), error,
                 prompt_tokens or 0, completion_tokens or 0, cost or 0.0))
            if error:
                self._conn.execute(
                    "UPDATE traces SET ended_at=MAX(COALESCE(ended_at,0),?),"
                    " status='error' WHERE id=?",
                    (ended_at, trace_id))
            else:
                self._conn.execute(
                    "UPDATE traces SET ended_at=MAX(COALESCE(ended_at,0),?)"
                    " WHERE id=?",
                    (ended_at, trace_id))
            self._conn.commit()
        return sid

    def list_traces(self, limit=100):
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT t.id, t.name, t.status, t.started_at, t.ended_at,"
                " COUNT(s.id) AS span_count,"
                " SUM(CASE WHEN s.error IS NOT NULL THEN 1 ELSE 0 END) AS error_count,"
                " COALESCE(SUM(s.prompt_tokens),0) AS prompt_tokens,"
                " COALESCE(SUM(s.completion_tokens),0) AS completion_tokens,"
                " COALESCE(SUM(s.cost),0) AS cost"
                " FROM traces t LEFT JOIN spans s ON s.trace_id = t.id"
                " GROUP BY t.id ORDER BY t.started_at DESC LIMIT ?",
                (limit,)).fetchall()
        traces = []
        for r in rows:
            d = dict(r)
            d["error_count"] = d["error_count"] or 0
            if d["status"] == "running":
                last = d["ended_at"] or d["started_at"]
                if now - last > RUNNING_IDLE_SECONDS:
                    d["status"] = "ok"
            traces.append(d)
        return traces

    def get_trace(self, tid):
        with self._lock:
            tr = self._conn.execute(
                "SELECT * FROM traces WHERE id=?", (tid,)).fetchone()
            if tr is None:
                return None
            spans = self._conn.execute(
                "SELECT * FROM spans WHERE trace_id=? ORDER BY idx", (tid,)).fetchall()
        trace = dict(tr)
        if trace["status"] == "running":
            last = trace["ended_at"] or trace["started_at"]
            if time.time() - last > RUNNING_IDLE_SECONDS:
                trace["status"] = "ok"
        out_spans = []
        for s in spans:
            d = dict(s)
            d["request"] = _loads(d.get("request"))
            d["response"] = _loads(d.get("response"))
            out_spans.append(d)
        return {"trace": trace, "spans": out_spans}

    def stats(self):
        now = time.time()
        day_start = now - 86400.0
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) AS traces FROM traces").fetchone()["traces"]
            row = self._conn.execute(
                "SELECT COUNT(s.id) AS spans,"
                " COALESCE(SUM(s.prompt_tokens),0) AS prompt_tokens,"
                " COALESCE(SUM(s.completion_tokens),0) AS completion_tokens,"
                " COALESCE(SUM(s.cost),0) AS cost,"
                " SUM(CASE WHEN s.error IS NOT NULL THEN 1 ELSE 0 END) AS errors"
                " FROM spans s").fetchone()
            today = self._conn.execute(
                "SELECT COUNT(s.id) AS spans,"
                " COALESCE(SUM(s.prompt_tokens),0) AS prompt_tokens,"
                " COALESCE(SUM(s.completion_tokens),0) AS completion_tokens,"
                " COALESCE(SUM(s.cost),0) AS cost"
                " FROM spans s WHERE s.started_at > ?",
                (day_start,)).fetchone()
        return {
            "traces": total,
            "spans": row["spans"],
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "cost": row["cost"],
            "errors": row["errors"] or 0,
            "today_spans": today["spans"],
            "today_cost": today["cost"],
            "today_prompt_tokens": today["prompt_tokens"],
            "today_completion_tokens": today["completion_tokens"],
        }

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM spans")
            self._conn.execute("DELETE FROM traces")
            self._conn.commit()


def _dumps(obj):
    import json
    if obj is None:
        return None
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"repr": repr(obj)}, ensure_ascii=False)


def _loads(text):
    import json
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return {"raw": text}

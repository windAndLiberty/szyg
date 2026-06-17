"""
智能评论数据库层 — 被 API routes 和 Engine 共享

封装所有 SQLite 操作，对外提供纯 Python 接口。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "comment_tasks.db"


def _get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表（幂等）"""
    conn = _get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS comment_tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target_platform TEXT NOT NULL,
            target_account TEXT NOT NULL,
            trigger_type TEXT DEFAULT 'new_video',
            trigger_keywords TEXT DEFAULT '[]',
            exclude_keywords TEXT DEFAULT '[]',
            status TEXT DEFAULT 'monitoring',
            status_entered_at TEXT,
            status_message TEXT,
            risk_level TEXT DEFAULT 'standard',
            daily_limit INTEGER DEFAULT 10,
            cooldown_seconds INTEGER DEFAULT 300,
            max_daily_per_target INTEGER DEFAULT 2,
            deduplicate INTEGER DEFAULT 1,
            persona TEXT DEFAULT '专业但友好的行业从业者',
            comment_style TEXT DEFAULT 'casual',
            max_length INTEGER DEFAULT 100,
            require_approval INTEGER DEFAULT 0,
            total_executed INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            total_deleted INTEGER DEFAULT 0,
            last_executed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            paused_until TEXT,
            auto_start INTEGER DEFAULT 0,
            schedule_cron TEXT
        );
        CREATE TABLE IF NOT EXISTS comment_records (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            target_video_id TEXT,
            target_comment_id TEXT,
            generated_text TEXT,
            final_text TEXT,
            status TEXT DEFAULT 'pending',
            platform_response TEXT,
            created_at TEXT,
            sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS state_transitions (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            event TEXT,
            reason TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON comment_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_records_task ON comment_records(task_id);
        CREATE INDEX IF NOT EXISTS idx_transitions_task ON state_transitions(task_id);
        """
    )
    conn.commit()
    conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["trigger_keywords"] = json.loads(d.get("trigger_keywords", "[]"))
    d["exclude_keywords"] = json.loads(d.get("exclude_keywords", "[]"))
    d["deduplicate"] = bool(d.get("deduplicate", 1))
    d["require_approval"] = bool(d.get("require_approval", 0))
    d["auto_start"] = bool(d.get("auto_start", 0))
    return d


# ── Task CRUD ──────────────────────────────────────────────────────


def create_task(task_data: dict) -> dict:
    conn = _get_db()
    conn.execute(
        """
        INSERT INTO comment_tasks VALUES (
            :id, :name, :target_platform, :target_account, :trigger_type,
            :trigger_keywords, :exclude_keywords, :status, :status_entered_at,
            :status_message, :risk_level, :daily_limit, :cooldown_seconds,
            :max_daily_per_target, :deduplicate, :persona, :comment_style,
            :max_length, :require_approval, :total_executed, :total_failed,
            :total_deleted, :last_executed_at, :created_at, :updated_at,
            :paused_until, :auto_start, :schedule_cron
        )
        """,
        {
            **{k: v for k, v in task_data.items() if k not in ("trigger_keywords", "exclude_keywords")},
            "trigger_keywords": json.dumps(task_data.get("trigger_keywords", [])),
            "exclude_keywords": json.dumps(task_data.get("exclude_keywords", [])),
            "deduplicate": int(task_data.get("deduplicate", True)),
            "require_approval": int(task_data.get("require_approval", False)),
            "auto_start": int(task_data.get("auto_start", False)),
        },
    )
    conn.commit()
    conn.close()
    return task_data


def get_task(task_id: str) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute("SELECT * FROM comment_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def list_tasks(status: Optional[str] = None, platform: Optional[str] = None, limit: int = 50, offset: int = 0) -> list:
    conn = _get_db()
    where = ["1=1"]
    params: dict = {}
    if status:
        where.append("status = :status")
        params["status"] = status
    if platform:
        where.append("target_platform = :platform")
        params["platform"] = platform
    sql = f"SELECT * FROM comment_tasks WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
    params.update({"limit": limit, "offset": offset})
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


def get_active_tasks() -> list:
    """获取所有需要引擎处理的任务（非终态）"""
    conn = _get_db()
    rows = conn.execute(
        """
        SELECT * FROM comment_tasks
        WHERE status IN ('monitoring', 'analyzing', 'generating', 'queued', 'follow_up')
        ORDER BY updated_at ASC
        """
    ).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


def update_task(task_id: str, updates: dict) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute("SELECT * FROM comment_tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return None

    set_values = {}
    for k, v in updates.items():
        if v is None:
            continue
        if k in ("trigger_keywords", "exclude_keywords"):
            set_values[k] = json.dumps(v)
        elif k in ("deduplicate", "require_approval", "auto_start"):
            set_values[k] = int(v)
        else:
            set_values[k] = v

    if set_values:
        set_values["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = :{k}" for k in set_values)
        conn.execute(f"UPDATE comment_tasks SET {sets} WHERE id = :id", {**set_values, "id": task_id})
        conn.commit()

    row = conn.execute("SELECT * FROM comment_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row_to_dict(row)


def delete_task(task_id: str):
    conn = _get_db()
    conn.execute("DELETE FROM comment_tasks WHERE id = ?", (task_id,))
    conn.execute("DELETE FROM comment_records WHERE task_id = ?", (task_id,))
    conn.execute("DELETE FROM state_transitions WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()


# ── State Transition ───────────────────────────────────────────────


def transition(task_id: str, to_status: str, reason: str = "", event: str = "engine") -> dict:
    """原子性状态转移：更新状态 + 记录审计日志"""
    conn = _get_db()
    row = conn.execute("SELECT status FROM comment_tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Task {task_id} not found")

    from_status = row["status"]
    now = datetime.now().isoformat()

    conn.execute(
        "INSERT INTO state_transitions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            f"ev_{int(datetime.now().timestamp() * 1000)}",
            task_id, from_status, to_status, event, reason,
            json.dumps({}), now,
        ),
    )
    conn.execute(
        "UPDATE comment_tasks SET status = ?, status_entered_at = ?, updated_at = ?, status_message = ? WHERE id = ?",
        (to_status, now, now, reason, task_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM comment_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row_to_dict(row)


# ── Comment Records ────────────────────────────────────────────────


def add_record(task_id: str, generated_text: str, final_text: str = "", status: str = "pending", video_id: str = "", comment_id: str = "") -> dict:
    record = {
        "id": f"cm_{int(datetime.now().timestamp() * 1000)}",
        "task_id": task_id,
        "target_video_id": video_id,
        "target_comment_id": comment_id,
        "generated_text": generated_text,
        "final_text": final_text or generated_text,
        "status": status,
        "created_at": datetime.now().isoformat(),
    }
    conn = _get_db()
    conn.execute(
        "INSERT INTO comment_records (id, task_id, target_video_id, target_comment_id, generated_text, final_text, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (record["id"], record["task_id"], record["target_video_id"], record["target_comment_id"],
         record["generated_text"], record["final_text"], record["status"], record["created_at"]),
    )
    conn.commit()
    conn.close()
    return record


def get_records(task_id: str, limit: int = 50) -> list:
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM comment_records WHERE task_id = ? ORDER BY created_at DESC LIMIT ?",
        (task_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_count(task_id: Optional[str] = None) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _get_db()
    if task_id:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM comment_records WHERE task_id = ? AND created_at LIKE ?",
            (task_id, f"{today}%"),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM comment_records WHERE created_at LIKE ?",
            (f"{today}%",),
        ).fetchone()
    conn.close()
    return row["c"]


# ── Transitions ────────────────────────────────────────────────────


def get_transitions(task_id: str, limit: int = 100) -> list:
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM state_transitions WHERE task_id = ? ORDER BY created_at DESC LIMIT ?",
        (task_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Dashboard ──────────────────────────────────────────────────────


def get_dashboard() -> dict:
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM comment_tasks").fetchone()["c"]
    active = conn.execute(
        "SELECT COUNT(*) as c FROM comment_tasks WHERE status IN ('monitoring', 'analyzing', 'generating', 'queued')"
    ).fetchone()["c"]
    paused = conn.execute("SELECT COUNT(*) as c FROM comment_tasks WHERE status = 'paused'").fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) as c FROM comment_tasks WHERE status = 'failed'").fetchone()["c"]
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = conn.execute(
        "SELECT COUNT(*) as c FROM comment_records WHERE created_at LIKE ?", (f"{today}%",)
    ).fetchone()["c"]
    platform_dist = conn.execute(
        "SELECT target_platform, COUNT(*) as c FROM comment_tasks GROUP BY target_platform"
    ).fetchall()
    conn.close()
    return {
        "total_tasks": total,
        "active_tasks": active,
        "paused_tasks": paused,
        "failed_tasks": failed,
        "today_executed": today_count,
        "platform_distribution": {r["target_platform"]: r["c"] for r in platform_dist},
    }

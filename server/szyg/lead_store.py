"""Lead Store — SQLite 线索存储 + FTS5 全文检索。"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from szyg.data_path import get_data_dir
from szyg.models.lead import (
    ConversionStage, IntentLevel, Interaction, LeadProfile, LeadSource
)


class LeadStore:
    """线索 SQLite 存储，支持 FTS5 全文搜索。"""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(get_data_dir() / "leads.db")
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._migrate()
        return self._conn

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                name TEXT,
                platform TEXT NOT NULL DEFAULT 'manual',
                platform_account TEXT DEFAULT '',
                company TEXT,
                industry TEXT,
                tags TEXT DEFAULT '[]',
                intent_score REAL DEFAULT 0.0,
                intent_level TEXT DEFAULT 'cold',
                conversion_stage TEXT DEFAULT 'discovered',
                interactions TEXT DEFAULT '[]',
                source_content TEXT,
                recommended_action TEXT,
                followup_deadline TEXT,
                assigned_to TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS leads_fts USING fts5(
                name, company, industry, platform_account, notes,
                content='leads', content_rowid='rowid'
            );
            CREATE INDEX IF NOT EXISTS idx_leads_intent ON leads(intent_level);
            CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(conversion_stage);
            CREATE INDEX IF NOT EXISTS idx_leads_platform ON leads(platform);
            CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry);
            CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at);
        """)

    # ── CRUD ─────────────────────────────────────────────

    def create(self, lead: LeadProfile) -> LeadProfile:
        now = datetime.utcnow().isoformat()
        lead.created_at = datetime.utcnow()
        lead.updated_at = datetime.utcnow()
        self.conn.execute(
            """INSERT INTO leads (id, name, platform, platform_account, company,
               industry, tags, intent_score, intent_level, conversion_stage,
               interactions, source_content, recommended_action,
               followup_deadline, assigned_to, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (lead.id, lead.name, lead.platform.value, lead.platform_account,
             lead.company, lead.industry, json.dumps(lead.tags, ensure_ascii=False),
             lead.intent_score, lead.intent_level.value, lead.conversion_stage.value,
             json.dumps([i.model_dump(mode='json') for i in lead.interactions], ensure_ascii=False, default=str),
             lead.source_content, lead.recommended_action,
             lead.followup_deadline.isoformat() if lead.followup_deadline else None,
             lead.assigned_to, lead.notes,
             lead.created_at.isoformat(), lead.updated_at.isoformat()),
        )
        self.conn.commit()
        return lead

    def get(self, lead_id: str) -> LeadProfile | None:
        row = self.conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return self._row_to_lead(row) if row else None

    def update(self, lead_id: str, **kwargs) -> LeadProfile | None:
        lead = self.get(lead_id)
        if not lead:
            return None
        for key, value in kwargs.items():
            if hasattr(lead, key):
                setattr(lead, key, value)
        lead.updated_at = datetime.utcnow()
        self.conn.execute(
            """UPDATE leads SET name=?, platform=?, platform_account=?, company=?,
               industry=?, tags=?, intent_score=?, intent_level=?, conversion_stage=?,
               interactions=?, source_content=?, recommended_action=?,
               followup_deadline=?, assigned_to=?, notes=?, updated_at=?
               WHERE id=?""",
            (lead.name, lead.platform.value, lead.platform_account,
             lead.company, lead.industry, json.dumps(lead.tags, ensure_ascii=False),
             lead.intent_score, lead.intent_level.value, lead.conversion_stage.value,
             json.dumps([i.model_dump(mode='json') for i in lead.interactions], ensure_ascii=False, default=str),
             lead.source_content, lead.recommended_action,
             lead.followup_deadline.isoformat() if lead.followup_deadline else None,
             lead.assigned_to, lead.notes, lead.updated_at.isoformat(), lead.id),
        )
        self.conn.commit()
        return lead

    def delete(self, lead_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def list_leads(
        self,
        intent_level: IntentLevel | None = None,
        stage: ConversionStage | None = None,
        platform: LeadSource | None = None,
        industry: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LeadProfile]:
        query = "SELECT * FROM leads WHERE 1=1"
        params: list = []
        if intent_level:
            query += " AND intent_level=?"
            params.append(intent_level.value)
        if stage:
            query += " AND conversion_stage=?"
            params.append(stage.value)
        if platform:
            query += " AND platform=?"
            params.append(platform.value)
        if industry:
            query += " AND industry=?"
            params.append(industry)
        query += " ORDER BY intent_score DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_lead(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[LeadProfile]:
        rows = self.conn.execute(
            """SELECT l.* FROM leads l
               JOIN leads_fts fts ON l.rowid = fts.rowid
               WHERE leads_fts MATCH ? ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [self._row_to_lead(r) for r in rows]

    def stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        by_intent = {}
        for row in self.conn.execute(
            "SELECT intent_level, COUNT(*) as cnt FROM leads GROUP BY intent_level"
        ).fetchall():
            by_intent[row["intent_level"]] = row["cnt"]
        by_stage = {}
        for row in self.conn.execute(
            "SELECT conversion_stage, COUNT(*) as cnt FROM leads GROUP BY conversion_stage"
        ).fetchall():
            by_stage[row["conversion_stage"]] = row["cnt"]
        # Today's new leads
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_new = self.conn.execute(
            "SELECT COUNT(*) FROM leads WHERE created_at >= ?", (today,)
        ).fetchone()[0]
        return {
            "total": total,
            "today_new": today_new,
            "by_intent": by_intent,
            "by_stage": by_stage,
        }

    # ── Helpers ──────────────────────────────────────────

    def _row_to_lead(self, row: sqlite3.Row) -> LeadProfile:
        interactions_raw = json.loads(row["interactions"] or "[]")
        interactions = []
        for i in interactions_raw:
            if isinstance(i.get("timestamp"), str):
                i["timestamp"] = datetime.fromisoformat(i["timestamp"])
            interactions.append(Interaction(**i))
        return LeadProfile(
            id=row["id"],
            name=row["name"],
            platform=LeadSource(row["platform"]),
            platform_account=row["platform_account"] or "",
            company=row["company"],
            industry=row["industry"],
            tags=json.loads(row["tags"] or "[]"),
            intent_score=row["intent_score"],
            intent_level=IntentLevel(row["intent_level"]),
            conversion_stage=ConversionStage(row["conversion_stage"]),
            interactions=interactions,
            source_content=row["source_content"],
            recommended_action=row["recommended_action"],
            followup_deadline=datetime.fromisoformat(row["followup_deadline"]) if row["followup_deadline"] else None,
            assigned_to=row["assigned_to"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# 全局单例
_store: LeadStore | None = None


def get_lead_store() -> LeadStore:
    global _store
    if _store is None:
        _store = LeadStore()
    return _store

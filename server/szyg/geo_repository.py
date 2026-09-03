"""Tenant-scoped SQLite persistence for GEO brand monitoring."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from szyg.atomic_file import atomic_read
from szyg.tenant import get_tenant_data_file


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class GeoRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_tenant_data_file("geo.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_schema(self) -> None:
        schema = """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS geo_meta (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS geo_questions (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL UNIQUE,
            topic TEXT NOT NULL DEFAULT '',
            intent TEXT NOT NULL DEFAULT 'discovery',
            importance INTEGER NOT NULL DEFAULT 2,
            source TEXT NOT NULL DEFAULT 'manual',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS geo_audits (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'diagnostic',
            provider_ids_json TEXT NOT NULL,
            question_ids_json TEXT NOT NULL,
            sample_count INTEGER NOT NULL DEFAULT 1,
            total INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT '',
            finished_at TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS ix_geo_audits_status ON geo_audits(status, created_at);
        CREATE TABLE IF NOT EXISTS geo_observations (
            id TEXT PRIMARY KEY,
            audit_id TEXT NOT NULL REFERENCES geo_audits(id) ON DELETE CASCADE,
            question_id TEXT NOT NULL REFERENCES geo_questions(id),
            provider_id TEXT NOT NULL,
            provider_label TEXT NOT NULL DEFAULT '',
            provider_model TEXT NOT NULL DEFAULT '',
            fidelity TEXT NOT NULL DEFAULT 'official_search_api',
            capture_method TEXT NOT NULL DEFAULT 'api',
            sample_index INTEGER NOT NULL DEFAULT 1,
            answer TEXT NOT NULL DEFAULT '',
            search_queries_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'queued',
            analysis_status TEXT NOT NULL DEFAULT 'pending',
            mentioned INTEGER NOT NULL DEFAULT 0,
            recommended INTEGER NOT NULL DEFAULT 0,
            recommendation_strength TEXT NOT NULL DEFAULT 'none',
            recommendation_evidence TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0,
            sentiment TEXT NOT NULL DEFAULT 'unknown',
            error TEXT NOT NULL DEFAULT '',
            latency_ms INTEGER NOT NULL DEFAULT 0,
            request_id TEXT NOT NULL DEFAULT '',
            observed_at TEXT NOT NULL,
            UNIQUE(audit_id, provider_id, question_id, sample_index)
        );
        CREATE INDEX IF NOT EXISTS ix_geo_observations_time ON geo_observations(observed_at DESC);
        CREATE INDEX IF NOT EXISTS ix_geo_observations_question ON geo_observations(question_id, provider_id);
        CREATE TABLE IF NOT EXISTS geo_citations (
            id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL REFERENCES geo_observations(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            normalized_url TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            snippet TEXT NOT NULL DEFAULT '',
            cited_text TEXT NOT NULL DEFAULT '',
            is_owned_domain INTEGER NOT NULL DEFAULT 0,
            UNIQUE(observation_id, normalized_url)
        );
        CREATE INDEX IF NOT EXISTS ix_geo_citations_domain ON geo_citations(domain);
        CREATE TABLE IF NOT EXISTS geo_competitor_mentions (
            id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL REFERENCES geo_observations(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            recommended INTEGER NOT NULL DEFAULT 0,
            evidence TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS geo_factual_issues (
            id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL REFERENCES geo_observations(id) ON DELETE CASCADE,
            claim TEXT NOT NULL,
            canonical_fact TEXT NOT NULL DEFAULT '',
            issue_type TEXT NOT NULL DEFAULT 'conflict',
            severity TEXT NOT NULL DEFAULT 'medium',
            evidence TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS geo_recommendations (
            id TEXT PRIMARY KEY,
            audit_id TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT NOT NULL DEFAULT 'medium',
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            rationale TEXT NOT NULL DEFAULT '',
            evidence_ids_json TEXT NOT NULL DEFAULT '[]',
            question_ids_json TEXT NOT NULL DEFAULT '[]',
            provider_ids_json TEXT NOT NULL DEFAULT '[]',
            evidence_count INTEGER NOT NULL DEFAULT 0,
            verification_audit_id TEXT NOT NULL DEFAULT '',
            verification_result_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_geo_recommendations_status ON geo_recommendations(status, created_at DESC);
        CREATE TABLE IF NOT EXISTS geo_canonical_facts (
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            value TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        with self._lock, self._connect() as conn:
            conn.executescript(schema)
            conn.execute("INSERT OR REPLACE INTO geo_meta(key, value) VALUES('schema_version', '1')")

    def get_meta(self, key: str) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM geo_meta WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else ""

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO geo_meta(key, value) VALUES(?, ?)", (key, value))

    def ensure_question(self, text: str, **meta: Any) -> dict[str, Any]:
        clean = str(text).strip()
        if not clean:
            raise ValueError("客户问题不能为空")
        now = _now()
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM geo_questions WHERE text=?", (clean,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE geo_questions SET topic=?, intent=?, importance=?, source=?, active=1, updated_at=? WHERE id=?",
                    (
                        str(meta.get("topic") or row["topic"]),
                        str(meta.get("intent") or row["intent"]),
                        max(1, min(3, int(meta.get("importance") or row["importance"] or 2))),
                        str(meta.get("source") or row["source"]), now, row["id"],
                    ),
                )
                question_id = str(row["id"])
            else:
                question_id = str(meta.get("id") or f"geoq_{uuid.uuid4().hex[:12]}")
                conn.execute(
                    "INSERT INTO geo_questions(id,text,topic,intent,importance,source,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (question_id, clean, str(meta.get("topic") or ""), str(meta.get("intent") or "discovery"),
                     max(1, min(3, int(meta.get("importance") or 2))), str(meta.get("source") or "manual"), 1, now, now),
                )
        return self.get_question(question_id) or {}

    def replace_questions(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        clean: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items[:100]:
            text = str(item.get("text") or "").strip()
            if not 4 <= len(text) <= 300 or text in seen:
                continue
            seen.add(text)
            clean.append({**item, "text": text})
        if not clean:
            raise ValueError("请至少保留一个客户问题")
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE geo_questions SET active=0, updated_at=?", (_now(),))
        return [self.ensure_question(**item) for item in clean]

    def get_question(self, question_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM geo_questions WHERE id=?", (question_id,)).fetchone()
        return dict(row) if row else None

    def list_questions(self, active_only: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM geo_questions"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY importance DESC, created_at"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [{**dict(row), "active": bool(row["active"])} for row in rows]

    def replace_facts(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM geo_canonical_facts")
            for item in items[:200]:
                subject = str(item.get("subject") or "").strip()
                predicate = str(item.get("predicate") or "").strip()
                value = str(item.get("value") or "").strip()
                if not subject or not predicate or not value:
                    continue
                conn.execute(
                    "INSERT INTO geo_canonical_facts VALUES(?,?,?,?,?,?,?,?)",
                    (str(item.get("id") or f"geof_{uuid.uuid4().hex[:12]}"), subject, predicate, value,
                     str(item.get("source_url") or ""), 1, now, now),
                )
        return self.list_facts()

    def list_facts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM geo_canonical_facts WHERE active=1 ORDER BY created_at").fetchall()
        return [{**dict(row), "active": bool(row["active"])} for row in rows]

    def insert_audit(self, audit: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO geo_audits VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (audit["id"], audit["status"], audit.get("mode", "diagnostic"), _json(audit["provider_ids"]),
                 _json(audit["question_ids"]), int(audit.get("sample_count") or 1), int(audit.get("total") or 0),
                 int(audit.get("completed") or 0), int(audit.get("failed") or 0), audit.get("created_at") or _now(),
                 audit.get("started_at", ""), audit.get("finished_at", ""), audit.get("error", "")),
            )
        return self.get_audit(audit["id"]) or audit

    @staticmethod
    def _audit(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["provider_ids"] = _loads(item.pop("provider_ids_json"), [])
        item["question_ids"] = _loads(item.pop("question_ids_json"), [])
        return item

    def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM geo_audits WHERE id=?", (audit_id,)).fetchone()
        return self._audit(row) if row else None

    def update_audit(self, audit_id: str, **values: Any) -> dict[str, Any]:
        allowed = {"status", "completed", "failed", "started_at", "finished_at", "error"}
        patch = {key: value for key, value in values.items() if key in allowed}
        if patch:
            clause = ",".join(f"{key}=?" for key in patch)
            with self._lock, self._connect() as conn:
                conn.execute(f"UPDATE geo_audits SET {clause} WHERE id=?", (*patch.values(), audit_id))
        item = self.get_audit(audit_id)
        if not item:
            raise KeyError(audit_id)
        return item

    def recover_audits(self) -> int:
        with self._lock, self._connect() as conn:
            cursor = conn.execute("UPDATE geo_audits SET status='queued', error='' WHERE status='running'")
            return int(cursor.rowcount or 0)

    def list_queued_audits(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM geo_audits WHERE status='queued' ORDER BY created_at LIMIT ?", (limit,)).fetchall()
        return [self._audit(row) for row in rows]

    def list_audits(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM geo_audits ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
        return [self._audit(row) for row in rows]

    def insert_observation(self, item: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "id", "audit_id", "question_id", "provider_id", "provider_label", "provider_model", "fidelity",
            "capture_method", "sample_index", "answer", "search_queries_json", "status", "analysis_status",
            "mentioned", "recommended", "recommendation_strength", "recommendation_evidence", "position",
            "sentiment", "error", "latency_ms", "request_id", "observed_at",
        )
        values = (
            item["id"], item["audit_id"], item["question_id"], item["provider_id"], item.get("provider_label", ""),
            item.get("provider_model", ""), item.get("fidelity", "official_search_api"), item.get("capture_method", "api"),
            int(item.get("sample_index") or 1), item.get("answer", ""), _json(item.get("search_queries") or []),
            item.get("status", "completed"), item.get("analysis_status", "completed"), bool(item.get("mentioned")),
            bool(item.get("recommended")), item.get("recommendation_strength", "none"),
            item.get("recommendation_evidence", ""), int(item.get("position") or 0), item.get("sentiment", "unknown"),
            item.get("error", ""), int(item.get("latency_ms") or 0), item.get("request_id", ""), item.get("observed_at") or _now(),
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO geo_observations({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
                values,
            )
            conn.execute("DELETE FROM geo_citations WHERE observation_id=?", (item["id"],))
            conn.execute("DELETE FROM geo_competitor_mentions WHERE observation_id=?", (item["id"],))
            conn.execute("DELETE FROM geo_factual_issues WHERE observation_id=?", (item["id"],))
            for citation in item.get("citations") or []:
                conn.execute(
                    "INSERT OR IGNORE INTO geo_citations VALUES(?,?,?,?,?,?,?,?,?)",
                    (f"geoc_{uuid.uuid4().hex[:12]}", item["id"], citation.get("url", ""), citation.get("normalized_url", ""),
                     citation.get("domain", ""), citation.get("title", ""), citation.get("snippet", ""),
                     citation.get("cited_text", ""), bool(citation.get("is_owned_domain"))),
                )
            for mention in item.get("competitor_mentions") or []:
                conn.execute(
                    "INSERT INTO geo_competitor_mentions VALUES(?,?,?,?,?,?)",
                    (f"geocm_{uuid.uuid4().hex[:12]}", item["id"], mention.get("name", ""), int(mention.get("position") or 0),
                     bool(mention.get("recommended")), mention.get("evidence", "")),
                )
            for issue in item.get("factual_issues") or []:
                conn.execute(
                    "INSERT INTO geo_factual_issues VALUES(?,?,?,?,?,?,?)",
                    (f"geofi_{uuid.uuid4().hex[:12]}", item["id"], issue.get("claim", ""), issue.get("canonical_fact", ""),
                     issue.get("issue_type", "conflict"), issue.get("severity", "medium"), issue.get("evidence", "")),
                )
        return self.get_observation(item["id"]) or item

    def observation_exists(self, audit_id: str, provider_id: str, question_id: str, sample_index: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM geo_observations WHERE audit_id=? AND provider_id=? AND question_id=? AND sample_index=?",
                (audit_id, provider_id, question_id, sample_index),
            ).fetchone()
        return bool(row)

    def _hydrate_observations(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        if not rows:
            return []
        ids = [str(row["id"]) for row in rows]
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            citations = conn.execute(f"SELECT * FROM geo_citations WHERE observation_id IN ({placeholders})", ids).fetchall()
            competitors = conn.execute(f"SELECT * FROM geo_competitor_mentions WHERE observation_id IN ({placeholders})", ids).fetchall()
            issues = conn.execute(f"SELECT * FROM geo_factual_issues WHERE observation_id IN ({placeholders})", ids).fetchall()
        by_citation: dict[str, list[dict[str, Any]]] = {}
        by_competitor: dict[str, list[dict[str, Any]]] = {}
        by_issue: dict[str, list[dict[str, Any]]] = {}
        for row in citations:
            by_citation.setdefault(str(row["observation_id"]), []).append({**dict(row), "is_owned_domain": bool(row["is_owned_domain"])})
        for row in competitors:
            by_competitor.setdefault(str(row["observation_id"]), []).append({**dict(row), "recommended": bool(row["recommended"])})
        for row in issues:
            by_issue.setdefault(str(row["observation_id"]), []).append(dict(row))
        result = []
        for row in rows:
            item = dict(row)
            item["mentioned"] = bool(item["mentioned"])
            item["recommended"] = bool(item["recommended"])
            item["search_queries"] = _loads(item.pop("search_queries_json"), [])
            item["citations"] = by_citation.get(item["id"], [])
            item["competitor_mentions"] = by_competitor.get(item["id"], [])
            item["competitors_mentioned"] = [entry["name"] for entry in item["competitor_mentions"]]
            item["factual_issues"] = by_issue.get(item["id"], [])
            result.append(item)
        return result

    def get_observation(self, observation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT o.*,q.text AS question,q.topic,q.intent,q.importance FROM geo_observations o JOIN geo_questions q ON q.id=o.question_id WHERE o.id=?",
                (observation_id,),
            ).fetchone()
        items = self._hydrate_observations([row] if row else [])
        return items[0] if items else None

    def list_observations(self, *, audit_id: str = "", provider_id: str = "", question_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
        where, values = [], []
        for column, value in (("o.audit_id", audit_id), ("o.provider_id", provider_id), ("o.question_id", question_id)):
            if value:
                where.append(f"{column}=?")
                values.append(value)
        sql = "SELECT o.*,q.text AS question,q.topic,q.intent,q.importance FROM geo_observations o JOIN geo_questions q ON q.id=o.question_id"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY o.observed_at DESC LIMIT ?"
        values.append(max(1, min(limit, 5000)))
        with self._connect() as conn:
            rows = conn.execute(sql, values).fetchall()
        return self._hydrate_observations(rows)

    def replace_recommendations(self, audit_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM geo_recommendations WHERE audit_id=? AND status='open'", (audit_id,))
            for item in items:
                conn.execute(
                    "INSERT INTO geo_recommendations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (item.get("id") or f"geor_{uuid.uuid4().hex[:12]}", audit_id, item["category"], item.get("status", "open"),
                     item.get("priority", "medium"), item["title"], item.get("description", ""), item.get("rationale", ""),
                     _json(item.get("evidence_ids") or []), _json(item.get("question_ids") or []), _json(item.get("provider_ids") or []),
                     int(item.get("evidence_count") or len(item.get("evidence_ids") or [])), item.get("verification_audit_id", ""),
                     _json(item.get("verification_result") or {}), now, now),
                )
        return self.list_recommendations(audit_id=audit_id)

    @staticmethod
    def _recommendation(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for field in ("evidence_ids", "question_ids", "provider_ids", "verification_result"):
            item[field] = _loads(item.pop(f"{field}_json"), [] if field != "verification_result" else {})
        return item

    def list_recommendations(self, *, audit_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
        sql, values = "SELECT * FROM geo_recommendations", []
        if audit_id:
            sql += " WHERE audit_id=?"
            values.append(audit_id)
        sql += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC LIMIT ?"
        values.append(max(1, min(limit, 1000)))
        with self._connect() as conn:
            rows = conn.execute(sql, values).fetchall()
        return [self._recommendation(row) for row in rows]

    def get_recommendation(self, recommendation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM geo_recommendations WHERE id=?", (recommendation_id,)).fetchone()
        return self._recommendation(row) if row else None

    def update_recommendation(self, recommendation_id: str, **values: Any) -> dict[str, Any]:
        allowed = {"status", "verification_audit_id"}
        patch = {key: value for key, value in values.items() if key in allowed}
        if "verification_result" in values:
            patch["verification_result_json"] = _json(values["verification_result"] or {})
        patch["updated_at"] = _now()
        with self._lock, self._connect() as conn:
            clause = ",".join(f"{key}=?" for key in patch)
            conn.execute(f"UPDATE geo_recommendations SET {clause} WHERE id=?", (*patch.values(), recommendation_id))
        item = self.get_recommendation(recommendation_id)
        if not item:
            raise KeyError(recommendation_id)
        return item

    def source_summary(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT c.domain, COUNT(DISTINCT c.id) citation_count, MAX(c.is_owned_domain) owned_count,
                          COUNT(DISTINCT o.question_id) question_count, COUNT(DISTINCT o.provider_id) provider_count,
                          MAX(c.title) title, MAX(c.url) sample_url,
                          COUNT(DISTINCT CASE WHEN cm.id IS NOT NULL AND o.recommended=0 THEN o.id END) competitor_gap_count
                   FROM geo_citations c
                   JOIN geo_observations o ON o.id=c.observation_id AND o.status='completed'
                   LEFT JOIN geo_competitor_mentions cm ON cm.observation_id=o.id
                   WHERE o.fidelity='consumer_surface' AND o.capture_method='sidebar_browser' AND c.domain<>''
                   GROUP BY c.domain ORDER BY citation_count DESC LIMIT ?""",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [{**dict(row), "is_owned": bool(row["owned_count"])} for row in rows]

    def migrate_legacy(self, *, audits_path: Path, observations_path: Path, recommendations_path: Path, questions: list[str]) -> None:
        if self.get_meta("legacy_imported"):
            return
        for text in questions:
            if str(text).strip():
                self.ensure_question(str(text), source="legacy")
        audits = atomic_read(audits_path)
        for old in reversed(audits):
            if self.get_audit(str(old.get("id") or "")):
                continue
            question_ids = [self.ensure_question(text, source="legacy")["id"] for text in old.get("questions") or [] if str(text).strip()]
            providers = list(old.get("provider_ids") or [])
            try:
                self.insert_audit({
                    "id": str(old.get("id") or f"geo_{uuid.uuid4().hex[:12]}"), "status": old.get("status") or "completed",
                    "mode": "legacy", "provider_ids": providers, "question_ids": question_ids, "sample_count": 1,
                    "total": old.get("total") or len(providers) * len(question_ids), "completed": old.get("completed") or 0,
                    "failed": old.get("failed") or 0, "created_at": old.get("created_at") or _now(),
                    "started_at": old.get("started_at") or "", "finished_at": old.get("finished_at") or "", "error": old.get("error") or "",
                })
            except sqlite3.IntegrityError:
                pass
        for old in reversed(atomic_read(observations_path)):
            audit_id = str(old.get("audit_id") or "")
            if not self.get_audit(audit_id):
                continue
            question = self.ensure_question(str(old.get("question") or "历史客户问题"), source="legacy")
            urls = old.get("citations") or []
            self.insert_observation({
                "id": str(old.get("id") or f"obs_{uuid.uuid4().hex[:12]}"), "audit_id": audit_id, "question_id": question["id"],
                "provider_id": old.get("provider_id") or "legacy", "provider_label": old.get("provider_label") or "历史记录",
                "provider_model": old.get("model") or "", "fidelity": "plain_model", "capture_method": "legacy",
                "sample_index": 1, "answer": old.get("answer") or "", "status": old.get("status") or "completed",
                "analysis_status": "legacy", "mentioned": old.get("mentioned", False), "recommended": old.get("recommended", False),
                "recommendation_strength": "legacy", "position": old.get("position") or 0, "sentiment": old.get("sentiment") or "unknown",
                "error": old.get("error") or "", "observed_at": old.get("observed_at") or _now(),
                "citations": [{"url": str(url), "normalized_url": str(url)} for url in urls],
                "competitor_mentions": [{"name": name} for name in old.get("competitors_mentioned") or []],
                "factual_issues": old.get("factual_issues") or [],
            })
        legacy_recs = atomic_read(recommendations_path)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in legacy_recs:
            grouped.setdefault(str(item.get("audit_id") or "legacy"), []).append(item)
        for audit_id, items in grouped.items():
            if self.get_audit(audit_id):
                self.replace_recommendations(audit_id, items)
        self.set_meta("legacy_imported", _now())

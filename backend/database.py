"""RecoverAI — SQLite Persistence Layer."""
import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DATABASE_PATH = os.environ.get("DATABASE_PATH", "recoverai.db")

def get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", DATABASE_PATH)

def init_db(db_path: Optional[str] = None):
    """Initialize the SQLite database with the recovery_records table."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recovery_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT NOT NULL,
            customer_id TEXT,
            amount REAL,
            failure_type TEXT,
            opportunity_score INTEGER,
            selected_action TEXT,
            agent_reason TEXT,
            agent_confidence REAL,
            policy_allowed INTEGER,
            policy_reason TEXT,
            requires_escalation INTEGER,
            execution_status TEXT,
            execution_provider TEXT,
            execution_provider_reference TEXT,
            verification_status TEXT,
            recovered_amount REAL DEFAULT 0.0,
            full_result TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_recovery_record(payment_id: str, customer_id: str, amount: float,
                         failure_type: str, result: Dict[str, Any],
                         db_path: Optional[str] = None) -> int:
    """Persist a complete recovery result. Returns the row ID."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    
    recovery = result.get("recovery_analysis", {})
    agent = result.get("agent_decision", {})
    policy = result.get("policy_decision", {})
    execution = result.get("execution_result", {})
    verification = result.get("verification_result", {})
    
    now = datetime.now(timezone.utc).isoformat()
    
    cursor = conn.execute("""
        INSERT INTO recovery_records (
            payment_id, customer_id, amount, failure_type,
            opportunity_score, selected_action, agent_reason, agent_confidence,
            policy_allowed, policy_reason, requires_escalation,
            execution_status, execution_provider, execution_provider_reference,
            verification_status, recovered_amount,
            full_result, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payment_id, customer_id, amount, failure_type,
        recovery.get("opportunity_score"),
        agent.get("selected_action"),
        agent.get("reason"),
        agent.get("confidence"),
        1 if policy.get("allowed") else 0,
        policy.get("reason"),
        1 if policy.get("requires_escalation") else 0,
        execution.get("status"),
        execution.get("provider"),
        execution.get("provider_reference"),
        verification.get("verification_status"),
        verification.get("recovered_amount", 0.0),
        json.dumps(result),
        now
    ))
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id

def get_recovery_records(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent recovery records."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM recovery_records ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recovery_record_by_payment_id(payment_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent recovery record for a payment_id."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM recovery_records WHERE payment_id = ? ORDER BY id DESC LIMIT 1",
        (payment_id,)
    ).fetchone()
    conn.close()
    if row:
        record = dict(row)
        if record.get("full_result"):
            record["full_result"] = json.loads(record["full_result"])
        return record
    return None

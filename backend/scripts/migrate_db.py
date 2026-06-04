from __future__ import annotations

import sqlite3
from pathlib import Path
import os
import sys

# Add backend directory to path so we can resolve config/imports if needed
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_database_path


def get_existing_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def migrate(db_path: Path | None = None) -> None:
    target_path = db_path or get_database_path()
    print(f"Running SQLite migrations on: {target_path}")

    # Ensure parent folder exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(target_path))
    cursor = connection.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys=ON")

    # 1. Create segments table if missing
    if not table_exists(connection, "segments"):
        print("Creating table: segments")
        cursor.execute(
            """
            CREATE TABLE segments (
                id TEXT PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                pdm_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL
            )
            """
        )

    # Check if segments table is empty, and seed defaults if so
    cursor.execute("SELECT COUNT(*) FROM segments")
    if cursor.fetchone()[0] == 0:
        print("Seeding default segments into segments table...")
        from datetime import datetime, timezone
        from uuid import uuid4
        standard_segments = [
            ("AI_AUTOMATION", "AI Automation", "AI-AUTOMATION"),
            ("REVOPS", "RevOps", "REVOPS"),
            ("SEO", "SEO", "SEO"),
            ("WEBFLOW", "Webflow", "WEBFLOW"),
            ("ROBOTICS", "Robotics", "ROBOTICS"),
            ("HUMANOIDS", "Humanoids", "HUMANOIDS"),
            ("AUTOMATION", "Automation", "AUTOMATION"),
            ("WEB3", "Web3", "WEB3"),
            ("CREATOR_TOOLS", "Creator Tools", "CREATOR-TOOLS"),
            ("FINTECH", "Fintech", "FINTECH"),
        ]
        for code, label, pdm_code in standard_segments:
            seg_id = f"SEG-{uuid4().hex[:10].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO segments (id, code, label, pdm_code, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (seg_id, code, label, pdm_code, "ACTIVE", now_iso),
            )

    # 2. Add scoping/indexing fields to evidence_entries
    columns = get_existing_columns(connection, "evidence_entries")
    if columns:
        migrations_evidence = [
            ("pdm_code", "TEXT"),
            ("offer_id", "TEXT"),
            ("campaign_batch_id", "TEXT"),
            ("signal_code", "TEXT"),
            ("alpha_signal_code", "TEXT"),
        ]
        for name, col_type in migrations_evidence:
            if name not in columns:
                print(f"Adding column '{name}' to 'evidence_entries'")
                cursor.execute(f"ALTER TABLE evidence_entries ADD COLUMN {name} {col_type}")

    # 3. Add scoping fields to confidence_updates
    columns = get_existing_columns(connection, "confidence_updates")
    if columns:
        migrations_confidence = [
            ("pdm_code", "TEXT"),
            ("offer_id", "TEXT"),
            ("campaign_batch_id", "TEXT"),
            ("signal_code", "TEXT"),
            ("alpha_signal_code", "TEXT"),
        ]
        for name, col_type in migrations_confidence:
            if name not in columns:
                print(f"Adding column '{name}' to 'confidence_updates'")
                cursor.execute(f"ALTER TABLE confidence_updates ADD COLUMN {name} {col_type}")

    # 4. Create Indexes for Latest Scores and Outcomes queries
    # SQLite does "CREATE INDEX IF NOT EXISTS" natively
    print("Creating indexes on prospect_scores and campaign_outcomes...")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_prospect_scores_lookup ON prospect_scores (prospect_id, calculated_at DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaign_outcomes_lookup ON campaign_outcomes (prospect_id, recorded_at DESC)"
    )

    connection.commit()
    connection.close()
    print("SQLite migrations completed successfully.")


if __name__ == "__main__":
    migrate()

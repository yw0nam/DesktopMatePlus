from __future__ import annotations

from typing import Dict, Iterable, List

import psycopg2


class PostgreSQLVocabularyManager:
    """Controlled vocabulary manager backed by PostgreSQL."""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = self._normalize_config(db_config)
        self._initialize_database()

    def _normalize_config(self, db_config: Dict[str, str]) -> Dict[str, str]:
        config = dict(db_config)
        if "database" in config and "dbname" not in config:
            config["dbname"] = config.pop("database")
        if "port" in config:
            config["port"] = int(config["port"])
        return config

    def _get_connection(self) -> psycopg2.Connection:
        """Creates a new PostgreSQL connection."""
        return psycopg2.connect(**self.db_config)

    def _initialize_database(self):
        """Ensures the vocabulary table exists."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS controlled_vocabulary (
            id BIGSERIAL PRIMARY KEY,
            category TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_sql)
            conn.commit()

    def get_all_terms(self) -> List[str]:
        """Returns all categories from the vocabulary, sorted alphabetically."""
        query = "SELECT category FROM controlled_vocabulary ORDER BY category;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
        return [row[0] for row in rows]

    def term_exists(self, term: str) -> bool:
        """Checks if a term exists in the vocabulary using an indexed lookup."""
        query = "SELECT 1 FROM controlled_vocabulary WHERE category = %s LIMIT 1;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (term,))
                row = cur.fetchone()
        return row is not None

    def add_term(self, term: str) -> bool:
        """
        Adds a new term to the vocabulary if it doesn't already exist.
        This operation is atomic and safe for concurrent use due to UNIQUE constraint.
        Returns True if a new row was inserted, False otherwise.
        """
        query = (
            "INSERT INTO controlled_vocabulary (category) VALUES (%s) "
            "ON CONFLICT (category) DO NOTHING RETURNING id;"
        )
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (term,))
                inserted = cur.fetchone()
            conn.commit()
        return inserted is not None

    def ensure_categories(self, categories: Iterable[str]) -> List[str]:
        """Ensures each category exists in the vocabulary and returns cleaned names."""
        cleaned: List[str] = []
        categories = list(categories)
        if not categories:
            return cleaned

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                for category in categories:
                    if not isinstance(category, str):
                        continue
                    normalized = category.strip()
                    if not normalized:
                        continue

                    cur.execute(
                        "SELECT 1 FROM controlled_vocabulary WHERE category = %s LIMIT 1;",
                        (normalized,),
                    )
                    exists = cur.fetchone() is not None
                    if not exists:
                        cur.execute(
                            "INSERT INTO controlled_vocabulary (category) VALUES (%s) "
                            "ON CONFLICT (category) DO NOTHING;",
                            (normalized,),
                        )
                    cleaned.append(normalized)
            conn.commit()

        return cleaned

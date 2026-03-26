from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ArticleRecord
from .normalize import make_dedupe_key, sha256_text


class StateStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    dedupe_key TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    journal TEXT NOT NULL,
                    title TEXT NOT NULL,
                    doi TEXT,
                    canonical_url TEXT,
                    article_type TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    published_online TEXT,
                    published_print TEXT,
                    abstract TEXT,
                    relevance_status TEXT NOT NULL,
                    authors_json TEXT NOT NULL,
                    subjects_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles(published_date);
                CREATE INDEX IF NOT EXISTS idx_articles_first_seen_at ON articles(first_seen_at);
                CREATE TABLE IF NOT EXISTS sent_digests (
                    digest_key TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    message_id TEXT,
                    sent_at TEXT NOT NULL,
                    PRIMARY KEY (digest_key, recipient)
                );
                """
            )

    def upsert_articles(self, articles: list[ArticleRecord], seen_at: str) -> None:
        with self._connect() as connection:
            for article in articles:
                first_seen_at = article.first_seen_at or seen_at
                last_seen_at = article.last_seen_at or seen_at
                dedupe_key = make_dedupe_key(
                    article.doi,
                    article.canonical_url,
                    article.journal,
                    article.title,
                    article.published_date,
                )
                connection.execute(
                    """
                    INSERT INTO articles (
                        dedupe_key, source_id, journal, title, doi, canonical_url, article_type,
                        published_date, published_online, published_print, abstract, relevance_status,
                        authors_json, subjects_json, provenance_json, first_seen_at, last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dedupe_key) DO UPDATE SET
                        source_id = excluded.source_id,
                        journal = excluded.journal,
                        title = excluded.title,
                        doi = COALESCE(articles.doi, excluded.doi),
                        canonical_url = COALESCE(articles.canonical_url, excluded.canonical_url),
                        article_type = excluded.article_type,
                        published_date = excluded.published_date,
                        published_online = COALESCE(articles.published_online, excluded.published_online),
                        published_print = COALESCE(articles.published_print, excluded.published_print),
                        abstract = CASE
                            WHEN articles.abstract IS NULL OR articles.abstract = '' THEN excluded.abstract
                            ELSE articles.abstract
                        END,
                        relevance_status = excluded.relevance_status,
                        authors_json = CASE
                            WHEN articles.authors_json = '[]' THEN excluded.authors_json
                            ELSE articles.authors_json
                        END,
                        subjects_json = CASE
                            WHEN articles.subjects_json = '[]' THEN excluded.subjects_json
                            ELSE articles.subjects_json
                        END,
                        provenance_json = excluded.provenance_json,
                        first_seen_at = MIN(articles.first_seen_at, excluded.first_seen_at),
                        last_seen_at = MAX(articles.last_seen_at, excluded.last_seen_at)
                    """,
                    (
                        dedupe_key,
                        article.source_id,
                        article.journal,
                        article.title,
                        article.doi,
                        article.canonical_url,
                        article.article_type,
                        article.published_date,
                        article.published_online,
                        article.published_print,
                        article.abstract,
                        article.relevance_status,
                        json.dumps(article.authors, sort_keys=True),
                        json.dumps(article.subjects, sort_keys=True),
                        json.dumps(article.provenance, sort_keys=True),
                        first_seen_at,
                        last_seen_at,
                    ),
                )

    def get_articles_between(self, start_date: str, end_exclusive: str) -> list[ArticleRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM articles
                WHERE published_date >= ? AND published_date < ?
                ORDER BY published_date DESC, journal ASC, title ASC
                """,
                (start_date, end_exclusive),
            ).fetchall()
        return [self._row_to_article(row) for row in rows]

    def get_late_additions(
        self,
        published_before: str,
        first_seen_since: str,
        generated_at: str,
    ) -> list[ArticleRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM articles
                WHERE published_date < ?
                  AND first_seen_at >= ?
                  AND first_seen_at <= ?
                ORDER BY published_date DESC, journal ASC, title ASC
                """,
                (published_before, first_seen_since, generated_at),
            ).fetchall()
        return [self._row_to_article(row) for row in rows]

    def has_sent_digest(self, digest_key: str, recipient: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM sent_digests
                WHERE digest_key = ? AND recipient = ?
                """,
                (digest_key, recipient),
            ).fetchone()
        return row is not None

    def record_sent_digest(
        self,
        digest_key: str,
        recipient: str,
        subject: str,
        body: str,
        sent_at: str,
        message_id: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO sent_digests (
                    digest_key, recipient, subject, content_sha256, message_id, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    digest_key,
                    recipient,
                    subject,
                    sha256_text(body),
                    message_id,
                    sent_at,
                ),
            )

    def _row_to_article(self, row: sqlite3.Row) -> ArticleRecord:
        return ArticleRecord(
            source_id=row["source_id"],
            journal=row["journal"],
            title=row["title"],
            published_date=row["published_date"],
            article_type=row["article_type"],
            doi=row["doi"],
            canonical_url=row["canonical_url"],
            published_online=row["published_online"],
            published_print=row["published_print"],
            abstract=row["abstract"],
            relevance_status=row["relevance_status"],
            authors=json.loads(row["authors_json"]),
            subjects=json.loads(row["subjects_json"]),
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            provenance=json.loads(row["provenance_json"]),
        )

"""SQLite-backed repository registry."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from codestrata.application.knowledge.errors import (
    KnowledgeStoreError,
    RepositoryAliasConflictError,
    RepositoryIdentityConflictError,
    RepositoryIdentityError,
    RepositoryNotFoundError,
)
from codestrata.application.knowledge.identity import (
    NormalizedRepositoryIdentity,
    build_local_canonical_key,
    normalize_github_url_alias,
    normalize_identity_hints,
    normalize_local_path_alias,
)
from codestrata.application.knowledge.models import (
    RepositoryAliasRecord,
    RepositoryAliasType,
    RepositoryIdentityHints,
    RepositoryRecord,
)
from codestrata.domain.repository.enums import RepositorySourceType
from codestrata.repository_auth.exceptions import UnsupportedRepositoryUrlError
from codestrata.repository_auth.github_urls import parse_github_repository_url


class SqliteRepositoryRegistry:
    """Concrete ``RepositoryRegistry`` using an open SQLite connection."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def register_or_resolve(self, identity_hints: RepositoryIdentityHints) -> RepositoryRecord:
        try:
            normalized = normalize_identity_hints(identity_hints)
        except RepositoryIdentityError:
            raise
        except Exception as error:  # noqa: BLE001 - boundary
            raise RepositoryIdentityError(str(error)) from error

        try:
            return self._register_or_resolve(normalized)
        except (
            KnowledgeStoreError,
            RepositoryIdentityError,
            RepositoryIdentityConflictError,
            RepositoryNotFoundError,
            RepositoryAliasConflictError,
        ):
            raise
        except sqlite3.Error as error:
            raise KnowledgeStoreError(
                "Repository registration failed due to a storage error"
            ) from error

    def get_by_id(self, repository_id: str) -> RepositoryRecord | None:
        row = self._connection.execute(
            """
            SELECT repository_id, canonical_key, source_type, display_name,
                   created_at, updated_at
            FROM repositories
            WHERE repository_id = ?
            """,
            (repository_id.strip(),),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_by_canonical_key(self, canonical_key: str) -> RepositoryRecord | None:
        row = self._connection.execute(
            """
            SELECT repository_id, canonical_key, source_type, display_name,
                   created_at, updated_at
            FROM repositories
            WHERE canonical_key = ?
            """,
            (canonical_key.strip(),),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def resolve_alias(
        self,
        alias_type: RepositoryAliasType,
        alias_value: str,
    ) -> RepositoryRecord | None:
        normalized_value = self._normalize_alias_value(alias_type, alias_value)
        row = self._connection.execute(
            """
            SELECT r.repository_id, r.canonical_key, r.source_type, r.display_name,
                   r.created_at, r.updated_at
            FROM repository_aliases a
            JOIN repositories r ON r.repository_id = a.repository_id
            WHERE a.alias_type = ? AND a.alias_value = ?
            """,
            (alias_type.value, normalized_value),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def add_alias(
        self,
        repository_id: str,
        alias_type: RepositoryAliasType,
        alias_value: str,
    ) -> None:
        if self.get_by_id(repository_id) is None:
            raise RepositoryNotFoundError(f"Repository not found: {repository_id}")
        normalized_value = self._normalize_alias_value(alias_type, alias_value)
        try:
            with self._transaction():
                self._insert_alias(
                    repository_id=repository_id,
                    alias_type=alias_type,
                    alias_value=normalized_value,
                    created_at=self._now(),
                )
        except RepositoryAliasConflictError:
            raise
        except sqlite3.Error as error:
            raise KnowledgeStoreError("Failed to add repository alias") from error

    def list_aliases(self, repository_id: str) -> Sequence[RepositoryAliasRecord]:
        rows = self._connection.execute(
            """
            SELECT repository_id, alias_type, alias_value, created_at
            FROM repository_aliases
            WHERE repository_id = ?
            ORDER BY alias_type ASC, alias_value ASC
            """,
            (repository_id.strip(),),
        ).fetchall()
        return tuple(
            RepositoryAliasRecord(
                repository_id=str(row["repository_id"]),
                alias_type=RepositoryAliasType(str(row["alias_type"])),
                alias_value=str(row["alias_value"]),
                created_at=_parse_timestamp(str(row["created_at"])),
            )
            for row in rows
        )

    def list_repositories(self) -> Sequence[RepositoryRecord]:
        rows = self._connection.execute(
            """
            SELECT repository_id, canonical_key, source_type, display_name,
                   created_at, updated_at
            FROM repositories
            ORDER BY display_name COLLATE NOCASE ASC, canonical_key ASC
            """
        ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def _register_or_resolve(
        self,
        normalized: NormalizedRepositoryIdentity,
    ) -> RepositoryRecord:
        matches: dict[str, RepositoryRecord] = {}

        if normalized.canonical_key is not None:
            by_key = self.get_by_canonical_key(normalized.canonical_key)
            if by_key is not None:
                matches[by_key.repository_id] = by_key

        for alias in normalized.aliases:
            found = self.resolve_alias(alias.alias_type, alias.alias_value)
            if found is None:
                continue
            if alias.alias_type is RepositoryAliasType.LEGACY_REPOSITORY_KEY:
                # Soft alias: never merge distinct canonical repositories.
                # When a canonical key is present, ignore legacy unless it already
                # agrees with the canonical match. Without a canonical key, use
                # legacy only when it does not introduce a multi-repo conflict.
                if normalized.canonical_key is not None:
                    if found.repository_id not in matches:
                        continue
                    continue
                if matches and found.repository_id not in matches:
                    continue
                if not matches:
                    matches[found.repository_id] = found
                continue
            matches[found.repository_id] = found

        if len(matches) > 1:
            ids = ", ".join(sorted(matches))
            raise RepositoryIdentityConflictError(
                "Identity hints resolve to multiple repositories: "
                f"{ids}. Refusing to merge automatically."
            )

        if len(matches) == 1:
            existing = next(iter(matches.values()))
            return self._update_existing(existing, normalized)

        return self._create_new(normalized)

    def _update_existing(
        self,
        existing: RepositoryRecord,
        normalized: NormalizedRepositoryIdentity,
    ) -> RepositoryRecord:
        now = self._now()
        display_name = normalized.display_name
        try:
            with self._transaction():
                if display_name != existing.display_name:
                    self._connection.execute(
                        """
                        UPDATE repositories
                        SET display_name = ?, updated_at = ?
                        WHERE repository_id = ?
                        """,
                        (display_name, _format_timestamp(now), existing.repository_id),
                    )
                for alias in normalized.aliases:
                    self._insert_alias(
                        repository_id=existing.repository_id,
                        alias_type=alias.alias_type,
                        alias_value=alias.alias_value,
                        created_at=now,
                        skip_legacy_conflicts=True,
                    )
        except RepositoryAliasConflictError:
            raise
        except sqlite3.Error as error:
            raise KnowledgeStoreError("Failed to update repository identity") from error

        refreshed = self.get_by_id(existing.repository_id)
        if refreshed is None:  # pragma: no cover - transactional integrity
            raise KnowledgeStoreError("Repository disappeared after update")
        return refreshed

    def _create_new(self, normalized: NormalizedRepositoryIdentity) -> RepositoryRecord:
        repository_id = self._id_factory()
        if normalized.canonical_key is not None:
            canonical_key = normalized.canonical_key
            source_type = normalized.source_type
        else:
            canonical_key = build_local_canonical_key(repository_id)
            source_type = (
                normalized.source_type
                if normalized.source_type is not RepositorySourceType.GITHUB
                else RepositorySourceType.LOCAL
            )
        now = self._now()
        try:
            with self._transaction():
                self._connection.execute(
                    """
                    INSERT INTO repositories(
                        repository_id, canonical_key, source_type,
                        display_name, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repository_id,
                        canonical_key,
                        source_type.value,
                        normalized.display_name,
                        _format_timestamp(now),
                        _format_timestamp(now),
                    ),
                )
                for alias in normalized.aliases:
                    self._insert_alias(
                        repository_id=repository_id,
                        alias_type=alias.alias_type,
                        alias_value=alias.alias_value,
                        created_at=now,
                        skip_legacy_conflicts=True,
                    )
        except sqlite3.IntegrityError as error:
            raise RepositoryIdentityConflictError(
                f"Canonical key already exists: {canonical_key}"
            ) from error
        except sqlite3.Error as error:
            raise KnowledgeStoreError("Failed to create repository") from error

        created = self.get_by_id(repository_id)
        if created is None:  # pragma: no cover
            raise KnowledgeStoreError("Repository was not created")
        return created

    def _insert_alias(
        self,
        *,
        repository_id: str,
        alias_type: RepositoryAliasType,
        alias_value: str,
        created_at: datetime,
        skip_legacy_conflicts: bool = False,
    ) -> None:
        existing = self._connection.execute(
            """
            SELECT repository_id FROM repository_aliases
            WHERE alias_type = ? AND alias_value = ?
            """,
            (alias_type.value, alias_value),
        ).fetchone()
        if existing is not None:
            owner = str(existing["repository_id"])
            if owner == repository_id:
                return
            if (
                skip_legacy_conflicts
                and alias_type is RepositoryAliasType.LEGACY_REPOSITORY_KEY
            ):
                return
            raise RepositoryAliasConflictError(
                f"Alias {alias_type.value}={alias_value!r} is already bound to "
                f"repository {owner}"
            )
        self._connection.execute(
            """
            INSERT INTO repository_aliases(
                repository_id, alias_type, alias_value, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                repository_id,
                alias_type.value,
                alias_value,
                _format_timestamp(created_at),
            ),
        )

    def _normalize_alias_value(
        self,
        alias_type: RepositoryAliasType,
        alias_value: str,
    ) -> str:
        compact = alias_value.strip()
        if not compact:
            raise RepositoryIdentityError("alias_value must be nonempty")
        if alias_type is RepositoryAliasType.LOCAL_PATH:
            from pathlib import Path

            return normalize_local_path_alias(Path(compact))
        if alias_type is RepositoryAliasType.GITHUB_URL:
            try:
                parsed = parse_github_repository_url(compact)
            except UnsupportedRepositoryUrlError as error:
                raise RepositoryIdentityError(str(error)) from error
            return normalize_github_url_alias(parsed)
        if alias_type is RepositoryAliasType.LEGACY_REPOSITORY_KEY:
            return compact.lower()
        if alias_type is RepositoryAliasType.CANONICAL_KEY_ALIAS:
            return compact.lower()
        raise RepositoryIdentityError(f"Unsupported alias type: {alias_type}")

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise KnowledgeStoreError("clock must return timezone-aware UTC datetimes")
        return value.astimezone(UTC)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> RepositoryRecord:
        return RepositoryRecord(
            repository_id=str(row["repository_id"]),
            canonical_key=str(row["canonical_key"]),
            source_type=RepositorySourceType(str(row["source_type"])),
            display_name=str(row["display_name"]),
            created_at=_parse_timestamp(str(row["created_at"])),
            updated_at=_parse_timestamp(str(row["updated_at"])),
        )


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

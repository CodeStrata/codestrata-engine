"""File-backed repository registry."""

from __future__ import annotations

from collections.abc import Callable, Sequence
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
from codestrata.infrastructure.knowledge_store.file.codec import (
    aliases_document,
    aliases_from_document,
    repository_document,
    repository_from_document,
)
from codestrata.infrastructure.knowledge_store.file.indexes import (
    iter_repository_ids,
    load_valid_repository,
)
from codestrata.infrastructure.knowledge_store.file.layout import FileStorePaths
from codestrata.infrastructure.knowledge_store.io import atomic_write_json, read_json_file
from codestrata.repository_auth.exceptions import UnsupportedRepositoryUrlError
from codestrata.repository_auth.github_urls import parse_github_repository_url


class FileRepositoryRegistry:
    """Concrete ``RepositoryRegistry`` using versioned JSON manifests."""

    def __init__(
        self,
        paths: FileStorePaths,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._paths = paths
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._on_change = on_change or (lambda: None)

    def register_or_resolve(self, identity_hints: RepositoryIdentityHints) -> RepositoryRecord:
        try:
            normalized = normalize_identity_hints(identity_hints)
        except RepositoryIdentityError:
            raise
        except Exception as error:  # noqa: BLE001 - boundary
            raise RepositoryIdentityError(str(error)) from error
        return self._register_or_resolve(normalized)

    def get_by_id(self, repository_id: str) -> RepositoryRecord | None:
        try:
            document = load_valid_repository(self._paths, repository_id.strip())
        except KnowledgeStoreError:
            return None
        if document is None:
            return None
        return repository_from_document(document)

    def get_by_canonical_key(self, canonical_key: str) -> RepositoryRecord | None:
        wanted = canonical_key.strip()
        for repository_id in iter_repository_ids(self._paths):
            record = self.get_by_id(repository_id)
            if record is not None and record.canonical_key == wanted:
                return record
        return None

    def resolve_alias(
        self,
        alias_type: RepositoryAliasType,
        alias_value: str,
    ) -> RepositoryRecord | None:
        normalized_value = self._normalize_alias_value(alias_type, alias_value)
        for repository_id in iter_repository_ids(self._paths):
            for alias in self.list_aliases(repository_id):
                if alias.alias_type is alias_type and alias.alias_value == normalized_value:
                    return self.get_by_id(repository_id)
        return None

    def add_alias(
        self,
        repository_id: str,
        alias_type: RepositoryAliasType,
        alias_value: str,
    ) -> None:
        if self.get_by_id(repository_id) is None:
            raise RepositoryNotFoundError(f"Repository not found: {repository_id}")
        normalized_value = self._normalize_alias_value(alias_type, alias_value)
        aliases = list(self.list_aliases(repository_id))
        self._insert_alias(
            aliases,
            repository_id=repository_id,
            alias_type=alias_type,
            alias_value=normalized_value,
            created_at=self._now(),
        )
        self._write_aliases(repository_id, tuple(aliases))
        self._on_change()

    def list_aliases(self, repository_id: str) -> Sequence[RepositoryAliasRecord]:
        path = self._paths.aliases_path(repository_id)
        if not path.is_file():
            return ()
        try:
            document = read_json_file(
                path,
                root=self._paths.root,
                max_bytes=self._paths.max_json_bytes,
            )
            return aliases_from_document(document)
        except (KnowledgeStoreError, KeyError, ValueError, TypeError):
            return ()

    def list_repositories(self) -> Sequence[RepositoryRecord]:
        records = [
            record
            for repository_id in iter_repository_ids(self._paths)
            if (record := self.get_by_id(repository_id)) is not None
        ]
        return tuple(
            sorted(records, key=lambda item: (item.display_name.lower(), item.canonical_key))
        )

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
        updated = existing
        if display_name != existing.display_name:
            updated = existing.model_copy(update={"display_name": display_name, "updated_at": now})
            self._write_repository(updated)
        aliases = list(self.list_aliases(existing.repository_id))
        for alias in normalized.aliases:
            self._insert_alias(
                aliases,
                repository_id=existing.repository_id,
                alias_type=alias.alias_type,
                alias_value=alias.alias_value,
                created_at=now,
                skip_legacy_conflicts=True,
            )
        self._write_aliases(existing.repository_id, tuple(aliases))
        self._on_change()
        refreshed = self.get_by_id(existing.repository_id)
        if refreshed is None:
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
        if self.get_by_canonical_key(canonical_key) is not None:
            raise RepositoryIdentityConflictError(f"Canonical key already exists: {canonical_key}")
        now = self._now()
        created = RepositoryRecord(
            repository_id=repository_id,
            canonical_key=canonical_key,
            source_type=source_type,
            display_name=normalized.display_name,
            created_at=now,
            updated_at=now,
        )
        self._paths.repository_dir(repository_id).mkdir(parents=True, exist_ok=True)
        self._write_repository(created)
        aliases: list[RepositoryAliasRecord] = []
        for alias in normalized.aliases:
            self._insert_alias(
                aliases,
                repository_id=repository_id,
                alias_type=alias.alias_type,
                alias_value=alias.alias_value,
                created_at=now,
                skip_legacy_conflicts=True,
            )
        self._write_aliases(repository_id, tuple(aliases))
        self._on_change()
        loaded = self.get_by_id(repository_id)
        if loaded is None:
            raise KnowledgeStoreError("Repository was not created")
        return loaded

    def _insert_alias(
        self,
        aliases: list[RepositoryAliasRecord],
        *,
        repository_id: str,
        alias_type: RepositoryAliasType,
        alias_value: str,
        created_at: datetime,
        skip_legacy_conflicts: bool = False,
    ) -> None:
        owner = self._owner_of_alias(alias_type, alias_value)
        if owner is not None:
            if owner == repository_id:
                return
            if skip_legacy_conflicts and alias_type is RepositoryAliasType.LEGACY_REPOSITORY_KEY:
                return
            raise RepositoryAliasConflictError(
                f"Alias {alias_type.value}={alias_value!r} is already bound to repository {owner}"
            )
        aliases.append(
            RepositoryAliasRecord(
                repository_id=repository_id,
                alias_type=alias_type,
                alias_value=alias_value,
                created_at=created_at,
            )
        )

    def _owner_of_alias(self, alias_type: RepositoryAliasType, alias_value: str) -> str | None:
        for repository_id in iter_repository_ids(self._paths):
            for alias in self.list_aliases(repository_id):
                if alias.alias_type is alias_type and alias.alias_value == alias_value:
                    return repository_id
        return None

    def _write_repository(self, record: RepositoryRecord) -> None:
        atomic_write_json(
            self._paths.repository_manifest(record.repository_id),
            repository_document(record),
            tmp_directory=self._paths.tmp,
            max_bytes=self._paths.max_json_bytes,
        )

    def _write_aliases(self, repository_id: str, records: Sequence[RepositoryAliasRecord]) -> None:
        atomic_write_json(
            self._paths.aliases_path(repository_id),
            aliases_document(records),
            tmp_directory=self._paths.tmp,
            max_bytes=self._paths.max_json_bytes,
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

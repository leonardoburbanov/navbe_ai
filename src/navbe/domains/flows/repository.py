"""Filesystem + SQLite persistence for flow specs."""

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    delete,
    insert,
    select,
    update,
)

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.flows.models import FlowMetadata, FlowSpec

metadata = MetaData()

flows_index = Table(
    "flows_index",
    metadata,
    Column("flow_id", String, primary_key=True),
    Column("name", String),
    Column("version", Integer, default=1),
    Column("path", String),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)


class FileSystemFlowRepository:
    """Store flow.json under flows_dir and index rows in SQLite."""

    def __init__(self, flows_dir: Path, session_factory: Any) -> None:
        """Create a repository over ``flows_dir`` and an async session factory."""
        self._flows_dir = flows_dir
        self._session_factory = session_factory

    def _flow_path(self, flow_id: str) -> Path:
        """Return the canonical flow.json path for ``flow_id``."""
        return self._flows_dir / flow_id / "flow.json"

    async def _write_spec(self, path: Path, flow_spec: FlowSpec) -> None:
        """Write a FlowSpec JSON file (by_alias)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(flow_spec.model_dump_json(by_alias=True, indent=2))

    async def save(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Persist a new flow (version 1) and index it."""
        path = self._flow_path(flow_spec.flow_id)
        if path.exists():
            raise ValidationError(
                f"Flow '{flow_spec.flow_id}' already exists",
                details={"flow_id": flow_spec.flow_id},
            )

        await self._write_spec(path, flow_spec)
        now = datetime.now(UTC).replace(tzinfo=None)

        async with self._session_factory() as session:
            await session.execute(
                insert(flows_index).values(
                    flow_id=flow_spec.flow_id,
                    name=flow_spec.name,
                    version=1,
                    path=str(path),
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        return FlowMetadata(
            flow_id=flow_spec.flow_id,
            name=flow_spec.name,
            created_at=now,
            updated_at=now,
            version=1,
            path=str(path),
        )

    async def get(self, flow_id: str) -> FlowSpec:
        """Load a FlowSpec from disk."""
        path = self._flow_path(flow_id)
        if not path.exists():
            raise NotFoundError(
                f"Flow '{flow_id}' not found",
                details={"flow_id": flow_id},
            )
        async with aiofiles.open(path, encoding="utf-8") as handle:
            content = await handle.read()
        return FlowSpec.model_validate_json(content)

    async def list(self) -> list[FlowMetadata]:
        """Return all indexed flow metadata."""
        async with self._session_factory() as session:
            result = await session.execute(select(flows_index))
            return [
                FlowMetadata(
                    flow_id=row.flow_id,
                    name=row.name,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    version=row.version,
                    path=row.path,
                )
                for row in result
            ]

    async def update(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Archive current flow.json, write new spec, and bump version."""
        path = self._flow_path(flow_spec.flow_id)
        if not path.exists():
            raise NotFoundError(
                f"Flow '{flow_spec.flow_id}' not found",
                details={"flow_id": flow_spec.flow_id},
            )

        async with self._session_factory() as session:
            result = await session.execute(
                select(flows_index).where(flows_index.c.flow_id == flow_spec.flow_id)
            )
            row = result.one_or_none()
            if row is None:
                raise NotFoundError(
                    f"Flow '{flow_spec.flow_id}' not found in index",
                    details={"flow_id": flow_spec.flow_id},
                )

            old_version = row.version
            created_at = row.created_at
            archive_path = path.parent / f"flow.v{old_version}.json"
            async with aiofiles.open(path, encoding="utf-8") as handle:
                previous = await handle.read()
            async with aiofiles.open(archive_path, "w", encoding="utf-8") as handle:
                await handle.write(previous)

            await self._write_spec(path, flow_spec)
            new_version = old_version + 1
            now = datetime.now(UTC).replace(tzinfo=None)
            await session.execute(
                update(flows_index)
                .where(flows_index.c.flow_id == flow_spec.flow_id)
                .values(
                    name=flow_spec.name,
                    version=new_version,
                    path=str(path),
                    updated_at=now,
                )
            )
            await session.commit()

        return FlowMetadata(
            flow_id=flow_spec.flow_id,
            name=flow_spec.name,
            created_at=created_at,
            updated_at=now,
            version=new_version,
            path=str(path),
        )

    async def upsert(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Write flow.json and upsert index without archival (for sync pull)."""
        path = self._flow_path(flow_spec.flow_id)
        await self._write_spec(path, flow_spec)
        now = datetime.now(UTC).replace(tzinfo=None)

        async with self._session_factory() as session:
            result = await session.execute(
                select(flows_index).where(flows_index.c.flow_id == flow_spec.flow_id)
            )
            row = result.one_or_none()
            if row is None:
                await session.execute(
                    insert(flows_index).values(
                        flow_id=flow_spec.flow_id,
                        name=flow_spec.name,
                        version=1,
                        path=str(path),
                        created_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()
                return FlowMetadata(
                    flow_id=flow_spec.flow_id,
                    name=flow_spec.name,
                    created_at=now,
                    updated_at=now,
                    version=1,
                    path=str(path),
                )

            created_at = row.created_at
            new_version = row.version
            await session.execute(
                update(flows_index)
                .where(flows_index.c.flow_id == flow_spec.flow_id)
                .values(
                    name=flow_spec.name,
                    path=str(path),
                    updated_at=now,
                )
            )
            await session.commit()

        return FlowMetadata(
            flow_id=flow_spec.flow_id,
            name=flow_spec.name,
            created_at=created_at,
            updated_at=now,
            version=new_version,
            path=str(path),
        )

    async def delete_index(self, flow_id: str) -> None:
        """Remove a flow_id from the SQLite index (disk dir already removed)."""
        async with self._session_factory() as session:
            await session.execute(
                delete(flows_index).where(flows_index.c.flow_id == flow_id)
            )
            await session.commit()

    async def delete(self, flow_id: str) -> None:
        """Remove ``flows/<flow_id>/`` and the index row."""
        flow_dir = self._flows_dir / flow_id
        path = self._flow_path(flow_id)
        async with self._session_factory() as session:
            result = await session.execute(
                select(flows_index.c.flow_id).where(flows_index.c.flow_id == flow_id)
            )
            indexed = result.one_or_none() is not None
        if not indexed and not path.exists():
            raise NotFoundError(
                f"Flow '{flow_id}' not found",
                details={"flow_id": flow_id},
            )
        if flow_dir.exists():
            shutil.rmtree(flow_dir)
        await self.delete_index(flow_id)

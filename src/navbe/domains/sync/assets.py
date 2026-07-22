"""Workspace sync assets — flows today; other kinds register later."""

from __future__ import annotations

import shutil
from pathlib import Path

import aiofiles

from navbe.domains.flows.interfaces import FlowRepository
from navbe.domains.flows.models import FlowSpec
from navbe.domains.sync.github_auth import AssetChangeSet


def list_flow_ids(flows_root: Path) -> list[str]:
    """Return flow_ids that have a ``flow.json`` under ``flows_root``."""
    if not flows_root.exists():
        return []
    ids: list[str] = []
    for child in sorted(flows_root.iterdir()):
        if child.is_dir() and (child / "flow.json").is_file():
            ids.append(child.name)
    return ids


def copy_flow_json(src_dir: Path, dest_dir: Path, flow_id: str) -> None:
    """Copy only ``flow_id/flow.json`` (creates dest dirs)."""
    src = src_dir / flow_id / "flow.json"
    dest = dest_dir / flow_id / "flow.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


class FlowsAsset:
    """Sync ``flows/<flow_id>/flow.json`` only (no runs/archives)."""

    subdir: str = "flows"

    def __init__(
        self,
        *,
        flows_dir: Path,
        flow_repository: FlowRepository,
    ) -> None:
        """Bind to local flows dir and repository."""
        self._flows_dir = flows_dir
        self._flows = flow_repository

    def list_local_ids(self) -> list[str]:
        """Return local flow ids that have flow.json."""
        return list_flow_ids(self._flows_dir)

    def list_remote_ids(self, clone_root: Path) -> list[str]:
        """Return flow ids present under clone ``flows/``."""
        return list_flow_ids(clone_root / self.subdir)

    def export_to(self, clone_root: Path) -> AssetChangeSet:
        """Copy local flow.json files into the clone; remove remote-only dirs."""
        remote_flows = clone_root / self.subdir
        remote_flows.mkdir(parents=True, exist_ok=True)

        local_ids = set(self.list_local_ids())
        remote_ids = set(list_flow_ids(remote_flows))

        removed = sorted(remote_ids - local_ids)
        for flow_id in removed:
            shutil.rmtree(remote_flows / flow_id, ignore_errors=True)

        added: list[str] = []
        updated: list[str] = []
        for flow_id in sorted(local_ids):
            if flow_id in remote_ids:
                updated.append(flow_id)
            else:
                added.append(flow_id)
            dest_dir = remote_flows / flow_id
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            copy_flow_json(self._flows_dir, remote_flows, flow_id)

        return AssetChangeSet(added=added, updated=updated, removed=removed)

    async def import_from(self, clone_root: Path) -> AssetChangeSet:
        """Import remote flow.json into Navbe; drop local flows absent on remote."""
        remote_flows = clone_root / self.subdir
        remote_ids = set(list_flow_ids(remote_flows))
        local_ids = set(self.list_local_ids())

        added: list[str] = []
        updated: list[str] = []
        for flow_id in sorted(remote_ids):
            spec_path = remote_flows / flow_id / "flow.json"
            async with aiofiles.open(spec_path, encoding="utf-8") as handle:
                raw = await handle.read()
            flow_spec = FlowSpec.model_validate_json(raw)
            if flow_id in local_ids:
                updated.append(flow_id)
            else:
                added.append(flow_id)
            await self._flows.upsert(flow_spec)

        removed = sorted(local_ids - remote_ids)
        for flow_id in removed:
            shutil.rmtree(self._flows_dir / flow_id, ignore_errors=True)
            await self._flows.delete_index(flow_id)

        return AssetChangeSet(added=added, updated=updated, removed=removed)

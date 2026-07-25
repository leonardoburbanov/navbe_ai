"""Subprocess git adapter — token only in-process, never written to disk."""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
from pathlib import Path

from navbe.core.exceptions import ExecutionError, ValidationError


class GitSubprocessRemote:
    """Git via ``git`` on PATH. Auth via ``http.extraHeader`` for the process only.

    ponytail: subprocess git — upgrade: pygit2 / GitHub Contents API.
    """

    def __init__(self, token: str | None = None) -> None:
        """Optional bearer token for HTTPS GitHub remotes."""
        self._token = token

    def with_token(self, token: str | None) -> GitSubprocessRemote:
        """Return a copy using ``token`` for subsequent commands."""
        return GitSubprocessRemote(token=token)

    def _auth_prefix(self) -> list[str]:
        """Git ``-c`` flags that inject auth without touching credential stores.

        GitHub App / user tokens authenticate as ``x-access-token:<token>``.
        Empty ``credential.helper`` stops Windows GCM from overriding the header
        with stale stored credentials (common cause of ``invalid credentials``).
        """
        if not self._token:
            return []
        basic = base64.b64encode(f"x-access-token:{self._token}".encode()).decode()
        return [
            "-c",
            "credential.helper=",
            "-c",
            f"http.extraHeader=AUTHORIZATION: basic {basic}",
        ]

    async def _run(
        self,
        args: list[str],
        *,
        cwd: str | None = None,
        check: bool = True,
    ) -> str:
        """Run a git command; raise ExecutionError on failure when ``check``."""
        env = os.environ.copy()
        # Avoid interactive prompts; never persist credentials.
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "never"
        cmd = ["git", *self._auth_prefix(), *args]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out_b, err_b = await proc.communicate()
        stdout = out_b.decode("utf-8", errors="replace").strip()
        stderr = err_b.decode("utf-8", errors="replace").strip()
        if check and proc.returncode != 0:
            raise ExecutionError(
                "git command failed",
                details={
                    "args": args,
                    "returncode": proc.returncode,
                    "stderr": stderr[:2000],
                },
            )
        return stdout

    async def ensure_clone(self, remote_url: str, local_dir: str, branch: str) -> None:
        """Clone if missing, otherwise fetch origin.

        Empty GitHub repos have no commits yet, so ``--branch`` fails. Plain clone
        then points HEAD at ``branch`` (unborn is fine until first push).
        """
        path = Path(local_dir)
        if path.exists() and (path / ".git").exists():
            await self._run(["fetch", "origin"], cwd=local_dir, check=False)
            await self._ensure_local_branch(local_dir, branch)
            return
        if path.exists():
            if any(path.iterdir()):
                raise ValidationError(
                    "local_repo_dir exists but is not a git clone",
                    details={"local_repo_dir": local_dir},
                )
            path.rmdir()
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            await self._run(
                ["clone", "--branch", branch, "--single-branch", remote_url, local_dir]
            )
        except ExecutionError as exc:
            stderr = str((exc.details or {}).get("stderr", "")).lower()
            if "not found" not in stderr and "does not match" not in stderr:
                raise
            if path.exists():
                shutil.rmtree(path)
            await self._run(["clone", remote_url, local_dir])
            await self._ensure_local_branch(local_dir, branch)

    async def _ensure_local_branch(self, local_dir: str, branch: str) -> None:
        """Checkout ``branch``, or set unborn HEAD for an empty clone."""
        current = await self._run(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=local_dir,
            check=False,
        )
        if current == branch:
            return
        try:
            await self._run(["checkout", branch], cwd=local_dir)
            return
        except ExecutionError:
            pass
        try:
            await self._run(["checkout", "-B", branch], cwd=local_dir)
            return
        except ExecutionError:
            # No commits yet — name the unborn branch.
            await self._run(
                ["symbolic-ref", "HEAD", f"refs/heads/{branch}"],
                cwd=local_dir,
            )

    async def current_branch(self, local_dir: str) -> str:
        """Return the checked-out branch name (works for unborn empty repos)."""
        name = await self._run(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=local_dir,
            check=False,
        )
        if name and name != "HEAD":
            return name
        ref = await self._run(["symbolic-ref", "--short", "HEAD"], cwd=local_dir)
        return ref

    async def is_dirty(self, local_dir: str) -> bool:
        """True if the working tree has uncommitted changes."""
        status = await self._run(["status", "--porcelain"], cwd=local_dir)
        return bool(status)

    async def create_branch(self, local_dir: str, name: str, from_branch: str) -> None:
        """Create ``name`` from ``from_branch`` and check it out."""
        await self._run(["fetch", "origin"], cwd=local_dir)
        await self._run(["checkout", from_branch], cwd=local_dir)
        await self._run(["pull", "--ff-only", "origin", from_branch], cwd=local_dir)
        await self._run(["checkout", "-b", name], cwd=local_dir)

    async def checkout(self, local_dir: str, branch: str) -> None:
        """Check out ``branch``."""
        await self._run(["checkout", branch], cwd=local_dir)

    async def pull_ff_only(self, local_dir: str, branch: str) -> str:
        """Fast-forward pull; return HEAD sha."""
        await self._run(["fetch", "origin"], cwd=local_dir)
        await self._run(["checkout", branch], cwd=local_dir)
        await self._run(["pull", "--ff-only", "origin", branch], cwd=local_dir)
        return await self.head_sha(local_dir)

    async def commit_all(
        self,
        local_dir: str,
        message: str,
        paths: list[str] | None = None,
    ) -> str | None:
        """Stage ``paths`` (or whole tree) and commit if dirty; return sha or None."""
        if paths:
            for path in paths:
                await self._run(["add", "-A", "--", path], cwd=local_dir)
        else:
            await self._run(["add", "-A"], cwd=local_dir)
        status = await self._run(["status", "--porcelain"], cwd=local_dir)
        if not status:
            return None
        await self._run(
            ["-c", "user.email=navbe@local", "-c", "user.name=Navbe", "commit", "-m", message],
            cwd=local_dir,
        )
        return await self.head_sha(local_dir)

    async def push(self, local_dir: str, branch: str) -> None:
        """Push current branch to origin."""
        await self._run(["push", "-u", "origin", branch], cwd=local_dir)

    async def head_sha(self, local_dir: str) -> str:
        """Return HEAD commit sha."""
        return await self._run(["rev-parse", "HEAD"], cwd=local_dir)

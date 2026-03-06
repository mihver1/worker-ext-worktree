from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from worker_core.extensions import ExtensionContext

from worker_ext_worktree import WorktreeExtension
from worker_ext_worktree.service import WorktreeManager


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    _git(repo, "branch", "-M", "main")


def _extension_for(project_dir: Path) -> WorktreeExtension:
    extension = WorktreeExtension()
    extension.bind_context(ExtensionContext(project_dir=str(project_dir), runtime="local"))
    return extension


@pytest.mark.asyncio
async def test_wt_without_branch_creates_detached_worktree(monkeypatch, tmp_path: Path) -> None:
    managed_root = tmp_path / "managed"
    repo = tmp_path / "repo"
    monkeypatch.setenv("WORKER_EXT_WORKTREE_BASE_DIR", str(managed_root))
    _init_repo(repo)

    extension = _extension_for(repo)
    output = await extension._cmd_wt("")

    assert output is not None
    assert "checkout: detached" in output
    assert "source: main" in output

    manager = WorktreeManager(str(repo))
    managed_worktrees = [
        worktree
        for worktree in manager.list_worktrees()
        if worktree.path != manager.primary_worktree
    ]
    assert len(managed_worktrees) == 1
    assert managed_worktrees[0].detached is True
    assert managed_worktrees[0].path.is_relative_to(managed_root / repo.name)


@pytest.mark.asyncio
async def test_wt_branch_creates_managed_branch_worktree_and_lists_it(
    monkeypatch,
    tmp_path: Path,
) -> None:
    managed_root = tmp_path / "managed"
    repo = tmp_path / "repo"
    monkeypatch.setenv("WORKER_EXT_WORKTREE_BASE_DIR", str(managed_root))
    _init_repo(repo)

    extension = _extension_for(repo)
    create_output = await extension._cmd_wt("feature/demo")
    assert create_output is not None
    assert "checkout: branch feature/demo" in create_output

    list_output = await extension._cmd_wt("list")
    assert list_output is not None
    assert "feature/demo" in list_output
    assert str(repo) in list_output

    manager = WorktreeManager(str(repo))
    managed_worktrees = [
        worktree
        for worktree in manager.list_worktrees()
        if worktree.path != manager.primary_worktree
    ]
    assert len(managed_worktrees) == 1
    assert managed_worktrees[0].branch == "feature/demo"
    assert managed_worktrees[0].path.is_relative_to(managed_root / repo.name)


@pytest.mark.asyncio
async def test_wt_rm_removes_managed_worktree_by_unique_subpath(
    monkeypatch,
    tmp_path: Path,
) -> None:
    managed_root = tmp_path / "managed"
    repo = tmp_path / "repo"
    monkeypatch.setenv("WORKER_EXT_WORKTREE_BASE_DIR", str(managed_root))
    _init_repo(repo)

    extension = _extension_for(repo)
    await extension._cmd_wt("feature/remove")

    manager = WorktreeManager(str(repo))
    created_worktree = next(
        worktree
        for worktree in manager.list_worktrees()
        if worktree.path != manager.primary_worktree
    )
    unique_subpath = created_worktree.path.name.rsplit("_", maxsplit=1)[-1]

    remove_output = await extension._cmd_wt(f"rm {unique_subpath}")
    assert remove_output == f"Removed worktree: {created_worktree.path}"
    assert created_worktree.path.exists() is False
    remaining_worktrees = manager.list_worktrees()
    assert [
        worktree
        for worktree in remaining_worktrees
        if worktree.path != manager.primary_worktree
    ] == []


@pytest.mark.asyncio
async def test_wt_finish_fast_forwards_managed_branch_into_current_branch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    managed_root = tmp_path / "managed"
    repo = tmp_path / "repo"
    monkeypatch.setenv("WORKER_EXT_WORKTREE_BASE_DIR", str(managed_root))
    _init_repo(repo)

    extension = _extension_for(repo)
    await extension._cmd_wt("feature/finish")

    manager = WorktreeManager(str(repo))
    source_worktree = next(
        worktree
        for worktree in manager.list_worktrees()
        if worktree.path != manager.primary_worktree
    )
    (source_worktree.path / "feature.txt").write_text("done\n", encoding="utf-8")
    _git(source_worktree.path, "add", "feature.txt")
    _git(source_worktree.path, "commit", "-m", "feature work")
    unique_subpath = source_worktree.path.name.rsplit("_", maxsplit=1)[-1]

    finish_output = await extension._cmd_wt(f"finish {unique_subpath}")
    assert finish_output is not None
    assert "source_branch: feature/finish" in finish_output
    assert "target_branch: main" in finish_output
    assert (repo / "feature.txt").read_text(encoding="utf-8") == "done\n"
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"


@pytest.mark.asyncio
async def test_wt_finish_rejects_detached_source_worktree(
    monkeypatch,
    tmp_path: Path,
) -> None:
    managed_root = tmp_path / "managed"
    repo = tmp_path / "repo"
    monkeypatch.setenv("WORKER_EXT_WORKTREE_BASE_DIR", str(managed_root))
    _init_repo(repo)

    extension = _extension_for(repo)
    await extension._cmd_wt("")

    manager = WorktreeManager(str(repo))
    source_worktree = next(
        worktree
        for worktree in manager.list_worktrees()
        if worktree.path != manager.primary_worktree
    )
    unique_subpath = source_worktree.path.name.rsplit("_", maxsplit=1)[-1]

    finish_output = await extension._cmd_wt(f"finish {unique_subpath}")
    assert (
        finish_output
        == "wt error: Cannot finish a detached worktree; create it from a branch first."
    )


@pytest.mark.asyncio
async def test_wt_finish_rejects_non_fast_forward_merge(
    monkeypatch,
    tmp_path: Path,
) -> None:
    managed_root = tmp_path / "managed"
    repo = tmp_path / "repo"
    monkeypatch.setenv("WORKER_EXT_WORKTREE_BASE_DIR", str(managed_root))
    _init_repo(repo)

    extension = _extension_for(repo)
    await extension._cmd_wt("feature/conflict")

    manager = WorktreeManager(str(repo))
    source_worktree = next(
        worktree
        for worktree in manager.list_worktrees()
        if worktree.path != manager.primary_worktree
    )
    (source_worktree.path / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(source_worktree.path, "add", "feature.txt")
    _git(source_worktree.path, "commit", "-m", "feature commit")

    (repo / "main.txt").write_text("main\n", encoding="utf-8")
    _git(repo, "add", "main.txt")
    _git(repo, "commit", "-m", "main commit")
    unique_subpath = source_worktree.path.name.rsplit("_", maxsplit=1)[-1]

    finish_output = await extension._cmd_wt(f"finish {unique_subpath}")
    assert (
        finish_output
        == "wt error: Fast-forward merge from feature/conflict into main is not possible."
    )

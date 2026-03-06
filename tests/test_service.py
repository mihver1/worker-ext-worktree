from __future__ import annotations

from pathlib import Path

import pytest

from worker_ext_worktree.service import (
    CreateCommand,
    FinishCommand,
    HelpCommand,
    ListCommand,
    RemoveCommand,
    WorktreeError,
    WorktreeInfo,
    format_worktree_list,
    parse_worktree_porcelain,
    parse_wt_command,
    resolve_remove_target,
)


def test_parse_wt_command_variants() -> None:
    assert parse_wt_command("") == CreateCommand()
    assert parse_wt_command("feature/demo") == CreateCommand(branch="feature/demo")
    assert parse_wt_command("list") == ListCommand()
    assert parse_wt_command("ls") == ListCommand()
    assert parse_wt_command("rm demo_a1b2c3") == RemoveCommand(target="demo_a1b2c3")
    assert parse_wt_command("finish demo_a1b2c3") == FinishCommand(target="demo_a1b2c3")
    assert parse_wt_command("merge demo_a1b2c3") == FinishCommand(target="demo_a1b2c3")
    assert parse_wt_command("help") == HelpCommand()


def test_parse_wt_command_rejects_invalid_remove_usage() -> None:
    with pytest.raises(WorktreeError, match="Usage: /wt rm <uniq_subpath>"):
        parse_wt_command("rm")


def test_parse_wt_command_rejects_invalid_finish_usage() -> None:
    with pytest.raises(WorktreeError, match="Usage: /wt finish <uniq_subpath>"):
        parse_wt_command("finish")


def test_parse_worktree_porcelain_parses_branch_and_detached_entries() -> None:
    parsed = parse_worktree_porcelain(
        "\n".join(
            [
                "worktree /tmp/repo",
                "HEAD abcdef1234567890",
                "branch refs/heads/main",
                "",
                "worktree /tmp/repo-feature",
                "HEAD fedcba0987654321",
                "detached",
                "",
            ]
        )
    )

    assert parsed == [
        WorktreeInfo(
            path=Path("/tmp/repo").resolve(),
            head="abcdef1234567890",
            branch="main",
        ),
        WorktreeInfo(
            path=Path("/tmp/repo-feature").resolve(),
            head="fedcba0987654321",
            branch=None,
            detached=True,
        ),
    ]


def test_resolve_remove_target_matches_unique_managed_subpath() -> None:
    primary = Path("/tmp/repo")
    managed_root = Path("/tmp/managed/repo")
    managed_path = managed_root / "feature_demo_a1b2c3"
    resolved = resolve_remove_target(
        "a1b2c3",
        worktrees=[
            WorktreeInfo(path=primary, head="abc", branch="main"),
            WorktreeInfo(path=managed_path, head="def", branch="feature/demo"),
        ],
        managed_root=managed_root,
        primary_worktree=primary,
    )

    assert resolved == managed_path.resolve()


def test_resolve_remove_target_rejects_ambiguous_fragment() -> None:
    primary = Path("/tmp/repo")
    managed_root = Path("/tmp/managed/repo")
    with pytest.raises(WorktreeError, match="Ambiguous worktree target"):
        resolve_remove_target(
            "feature",
            worktrees=[
                WorktreeInfo(path=primary, head="abc", branch="main"),
                WorktreeInfo(path=managed_root / "feature_one_a1b2c3", head="def"),
                WorktreeInfo(path=managed_root / "feature_two_d4e5f6", head="ghi"),
            ],
            managed_root=managed_root,
            primary_worktree=primary,
        )


def test_format_worktree_list_marks_primary_and_managed() -> None:
    primary = Path("/tmp/repo")
    managed_root = Path("/tmp/managed/repo")
    output = format_worktree_list(
        worktrees=[
            WorktreeInfo(path=primary, head="abcdef0", branch="main"),
            WorktreeInfo(
                path=managed_root / "feature_demo_a1b2c3",
                head="1234567",
                branch=None,
                detached=True,
            ),
        ],
        managed_root=managed_root,
        primary_worktree=primary,
    )

    assert "- main [primary]" in output
    assert "- detached [managed, detached]" in output

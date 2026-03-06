"""Worker extension entrypoint for git worktree management."""

from __future__ import annotations

import asyncio
import os
from typing import cast

from worker_core.extensions import CommandHandler, Extension, ExtensionContext

from worker_ext_worktree.service import (
    CreateCommand,
    FinishCommand,
    HelpCommand,
    ListCommand,
    RemoveCommand,
    WorktreeCommand,
    WorktreeError,
    WorktreeManager,
    format_create_result,
    format_finish_result,
    format_remove_result,
    format_worktree_list,
    parse_wt_command,
    usage_text,
)


class WorktreeExtension(Extension):
    """Expose git worktree helpers as the `/wt` slash command."""

    name = "wt"
    version = "0.1.0"

    def get_commands(self) -> dict[str, CommandHandler]:
        return {"wt": self._cmd_wt}

    async def _cmd_wt(self, arg: str) -> str | None:
        try:
            command = parse_wt_command(arg)
        except WorktreeError as exc:
            return f"wt error: {exc}\n\n{usage_text()}"

        manager = self._manager()
        try:
            return await asyncio.to_thread(self._execute_command, manager, command)
        except WorktreeError as exc:
            return f"wt error: {exc}"

    def _manager(self) -> WorktreeManager:
        context = self.context or ExtensionContext(project_dir=os.getcwd(), runtime="local")
        return WorktreeManager(project_dir=context.project_dir or os.getcwd())

    def _execute_command(
        self,
        manager: WorktreeManager,
        command: WorktreeCommand,
    ) -> str:
        if isinstance(command, HelpCommand):
            return usage_text()
        if isinstance(command, ListCommand):
            return format_worktree_list(
                worktrees=manager.list_worktrees(),
                managed_root=manager.managed_repo_dir,
                primary_worktree=manager.primary_worktree,
            )
        if isinstance(command, RemoveCommand):
            removed_path = manager.remove_worktree(command.target)
            return format_remove_result(removed_path)
        if isinstance(command, FinishCommand):
            finished = manager.finish_worktree(command.target)
            return format_finish_result(finished)

        create_command = cast(CreateCommand, command)
        created = manager.create_worktree(create_command.branch)
        return format_create_result(created)

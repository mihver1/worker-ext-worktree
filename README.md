# worker-ext-worktree
`worker-ext-worktree` is a Worker extension that adds a `/wt` slash command for managing git worktrees from the current repository.

## What it does
- Creates managed worktrees under `~/Projects/warp_worktrees/<repo>/...`
- Lists current repository worktrees
- Removes managed worktrees by a unique path fragment
- Handles the git limitation that the same branch cannot be checked out in two worktrees at once

## Installation
Install the extension into the same Python environment as Worker.

### Install from a local checkout
```bash
worker ext install /absolute/path/to/worker-ext-worktree
```

### Development setup
```bash
uv sync --dev
```

## Commands
The extension registers one slash command:

- `/wt [branch]`
- `/wt list`
- `/wt rm <uniq_subpath>`
- `/wt finish <uniq_subpath>`
- `/wt merge <uniq_subpath>` (alias for `finish`)
- `/wt help`

### `/wt [branch]`
Creates a new managed worktree.

Behavior:
- If `branch` is a new branch name, the extension creates that branch from the current `HEAD`.
- If `branch` already exists and is not checked out anywhere else, the extension creates a worktree on that branch.
- If `branch` is already checked out in another worktree, the extension creates a detached worktree from that branch tip.
- If `branch` is omitted, the extension creates a detached worktree from the current branch tip.

The detached fallback is necessary because git does not allow the same branch to be checked out in two worktrees at the same time.

### `/wt list`
Shows all worktrees for the current repository and marks them as:

- `primary` — the main checkout
- `managed` — created under the configured managed directory
- `external` — another linked worktree outside the managed directory

### `/wt rm <uniq_subpath>`
Removes a managed worktree by a unique fragment of its path. For example, if the path is:

```text
/Users/me/Projects/warp_worktrees/worker/feature_demo_a1b2c3
```

Then any unique fragment like `a1b2c3` or `feature_demo_a1b2c3` can be used.

### `/wt finish <uniq_subpath>`
Fast-forwards the source worktree branch into the current branch of the current checkout.

Safety rules:
- the current checkout must be on a branch
- the source worktree must be branch-backed, not detached
- both source and target worktrees must be clean
- merge is `--ff-only`, so divergent history is rejected

`/wt merge <uniq_subpath>` is an alias with the same behavior.

## Configuration
The managed worktree base directory defaults to:

```text
~/Projects/warp_worktrees
```

You can override it with one of these environment variables:

- `WORKER_EXT_WORKTREE_BASE_DIR`
- `WORKTREE_BASE_DIR`
- `WORKTREES_BASE`

## Auto mode idea
The current implementation focuses on explicit slash commands. A reasonable next step would be an auto mode that:

- creates a managed worktree on session start
- generates branch names like `worker/<simple-word>_<simple-word>`
- switches the session context into that worktree automatically
- cleans the worktree up when the session ends

This can be layered on top of the current service logic without changing the command contract.

## Development
### Run tests
```bash
uv run pytest
```

### Run lint
```bash
uv run ruff check .
```

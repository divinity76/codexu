# codexu

codex-cli auto-updater script, drop-in replacement for `codex` that runs a quick
update check before launching the CLI. It only installs the latest stable
release (skipping prerelease tags like `0.57.0-alpha.2`).

## Supported installs / platforms

- macOS / Linux installs managed by Homebrew (`brew upgrade --cask codex`)
- npm-based installs on any platform (`npm update -g @openai/codex`)
- Custom installs on Linux, macOS, or Windows (downloads the correct artifact
  and replaces the existing binary automatically)

## Installation

```sh
curl -fsSL https://raw.githubusercontent.com/divinity76/codexu/refs/heads/main/src/install.py | python -
```

The installer drops `codexu` (or `codexu.py`/`codexu.bat` on Windows) next to
your existing `codex` binary so you can invoke it directly.

## Usage

```
$ codexu
Updating Codex from 0.61.0 -> 0.63.0 using homebrew workflow.
Running: /home/linuxbrew/.linuxbrew/bin/brew upgrade --cask codex
==> Auto-updating Homebrew...
Adjust how often this is run with `$HOMEBREW_AUTO_UPDATE_SECS` or disable with
`$HOMEBREW_NO_AUTO_UPDATE=1`. Hide these hints with `$HOMEBREW_NO_ENV_HINTS=1` (see `man brew`).
==> Fetching downloads for: codex
✔︎ Cask codex (0.63.0)                                                                                                                                           [Verifying    20.0MB/ 20.0MB]
==> Upgrading 1 outdated package:
codex 0.61.0 -> 0.63.0
==> Upgrading codex
All dependencies satisfied.
==> Unlinking Binary '/home/linuxbrew/.linuxbrew/bin/codex'
==> Linking Binary 'codex-x86_64-unknown-linux-musl' to '/home/linuxbrew/.linuxbrew/bin/codex'
==> Purging files for version 0.61.0 of Cask codex
🍺  codex was successfully upgraded!
Codex updated to 0.63.0. Starting Codex...
╭────────────────────────────────────────────────────────╮
│ >_ OpenAI Codex (v0.63.0)                              │
│                                                        │
│ model:     gpt-5.1-codex-max medium   /model to change │
│ directory: ~/projects/wolfssh                          │
╰────────────────────────────────────────────────────────╯

  To get started, describe a task or try one of these commands:

  /init - create an AGENTS.md file with instructions for Codex
  /status - show current session configuration
  /approvals - choose what Codex can do without approval
  /model - choose what model and reasoning effort to use
  /review - review any changes and find issues

 
› Summarize recent commits
 
  100% context left · ? for shortcuts
```

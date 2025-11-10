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

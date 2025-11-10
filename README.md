# codexu

Utility that keeps your Codex CLI aligned with the latest release every time it
runs. It checks the locally installed version, compares it to GitHub's current
release, updates if necessary, then launches Codex.

## Supported installs / platforms

- macOS / Linux installs managed by Homebrew (`brew upgrade --cask codex`)
- npm-based installs on any platform (`npm update -g @openai/codex`)
- Custom installs on Linux, macOS, or Windows (downloads the correct artifact
  and replaces the existing binary automatically)

## Quick install

```sh
curl -fsSL https://raw.githubusercontent.com/divinity76/codexu/refs/heads/main/src/install.py | python -
```

The installer drops `codexu` (or `codexu.py`/`codexu.bat` on Windows) next to
your existing `codex` binary so you can invoke it directly.

## Manual usage

Clone the repo and run the updater script:

```sh
python src/codexu.py
```

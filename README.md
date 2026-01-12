# nanocode

Minimal Claude Code alternative with optional support for OpenAI’s Codex models.

The original version of **nanocode** was a single Python file (~250 lines)
that connected to Anthropic’s Claude models via the `/v1/messages` API and
implemented a simple agentic loop with tool use.  This fork extends the
project to work with OpenAI models (including Codex) by toggling the
`MODEL` environment variable and providing an appropriate API key.  When
`MODEL` names a Claude model (e.g. starts with `claude`) the script
continues to use the Anthropic API【911796291458355†L45-L49】.  When it names
an OpenAI model (e.g. `gpt-5-codex`), the script uses the OpenAI Chat
Completions or Responses API and authenticates with the `OPENAI_API_KEY`
environment variable【695241305770331†L199-L225】.

![screenshot](screenshot.png)

## Features

* Full agentic loop with tool use
* Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
* Conversation history
* Colored terminal output
* Supports both Anthropic and OpenAI models, including Codex

## Usage

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY="your-anthropic-key"
# Optionally override the model (defaults to claude-opus-4-5)
export MODEL="claude-opus-4-5"
python nanocode.py

# OpenAI / Codex
export OPENAI_API_KEY="your-openai-key"
export MODEL="gpt-5-codex"  # or any supported GPT/Codex model
python nanocode.py
```

The program inspects the value of `MODEL` to determine which backend to
use.  Claude models trigger the Anthropic API, while names beginning with
`gpt-` or containing `codex` cause the OpenAI API to be used.  See the
source for details.

## Commands

* `/c` – Clear conversation
* `/q` or `exit` – Quit

## Tools

| Tool | Description |
|------|-------------|
| `read` | Read file with line numbers, offset/limit |
| `write` | Write content to file |
| `edit` | Replace string in file (must be unique unless `all=true`) |
| `glob` | Find files by pattern, sorted by mtime |
| `grep` | Search files for regex |
| `bash` | Run shell command |

## Example

```
────────────────────────────────────────
❯ what files are here?
────────────────────────────────────────
⏺ Glob(**/*.py)
 ⎿ nanocode.py
⏺ There's one Python file: nanocode.py
```

## License

MIT
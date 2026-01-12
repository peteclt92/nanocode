#!/usr/bin/env python3
"""nanocode - minimal claude code alternative with Codex support

This script implements a simple interactive coding assistant.  It was
originally designed to use Anthropic’s Claude models via their
`/v1/messages` API but has been extended to support OpenAI’s Codex
models through the Chat Completions or Responses API.  The model to
use is determined by the value of the `MODEL` constant or the
corresponding environment variable.  When `MODEL` names a Claude
variant (e.g. begins with ``claude``) the Anthropic API is used and
authentication is performed via the `ANTHROPIC_API_KEY` environment
variable as before【911796291458355†L45-L49】.  When `MODEL` names an
OpenAI model (e.g. ``gpt-`` or ``codex``) the OpenAI API is used and
authentication is performed via the `OPENAI_API_KEY` environment
variable【695241305770331†L199-L225】.  See the README for details.
"""

import glob as globlib
import json
import os
import re
import subprocess
import urllib.request
from typing import Any, Dict, List


# Default API endpoint and model.  These values are overridden at
# runtime based on the selected model.
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

MODEL = os.environ.get("MODEL", "claude-opus-4-5")

# ANSI colours for terminal output
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)

# --- Tool implementations ---

def read(args: Dict[str, Any]) -> str:
    """Read a file and return selected lines with line numbers."""
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args: Dict[str, Any]) -> str:
    """Write content to a file."""
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args: Dict[str, Any]) -> str:
    """Replace occurrences of a string in a file."""
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob(args: Dict[str, Any]) -> str:
    """Find files matching a pattern and return them sorted by modification time."""
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


def grep(args: Dict[str, Any]) -> str:
    """Search files for lines matching a regular expression."""
    pattern = re.compile(args["pat"])
    hits: List[str] = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args: Dict[str, Any]) -> str:
    """Execute a shell command and return its output."""
    result = subprocess.run(
        args["cmd"], shell=True, capture_output=True, text=True, timeout=30
    )
    return (result.stdout + result.stderr).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---
TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name: str, args: Dict[str, Any]) -> str:
    """Dispatch to the appropriate tool function."""
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema() -> List[Dict[str, Any]]:
    """Create the tool schema expected by Anthropic."""
    result: List[Dict[str, Any]] = []
    for name, (description, params, _fn) in TOOLS.items():
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append(
            {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        )
    return result


def make_openai_tools() -> List[Dict[str, Any]]:
    """Convert the internal tool registry into the structure expected by OpenAI."""
    tools: List[Dict[str, Any]] = []
    for name, (description, params, _fn) in TOOLS.items():
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return tools


def convert_messages_to_openai(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Translate our internal message structure into OpenAI's format.

    The internal representation stores a sequence of messages.  User messages
    are simple strings, assistant messages are lists of content blocks
    (text or tool_use), and tool results are lists of result dictionaries.
    OpenAI expects a flat list of dicts with roles ``user``, ``assistant`` or
    ``tool`` and optional tool_calls/arguments fields.  This function
    performs the necessary transformation.
    """
    openai_msgs: List[Dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        # A plain user input
        if role == "user" and isinstance(content, str):
            openai_msgs.append({"role": "user", "content": content})
            continue
        # Assistant content blocks from a prior response
        if role == "assistant" and isinstance(content, list):
            for block in content:
                if block["type"] == "text":
                    openai_msgs.append(
                        {"role": "assistant", "content": block["text"]}
                    )
                elif block["type"] == "tool_use":
                    openai_msgs.append(
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": block["id"],
                                    "type": "function",
                                    "function": {
                                        "name": block["name"],
                                        "arguments": json.dumps(block["input"]),
                                    },
                                }
                            ],
                        }
                    )
            continue
        # Tool results provided by the user
        if role == "user" and isinstance(content, list):
            for tr in content:
                openai_msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr["tool_use_id"],
                        "content": tr["content"],
                    }
                )
            continue
    return openai_msgs


def call_api(messages: List[Dict[str, Any]], system_prompt: str) -> Dict[str, Any]:
    """Send a request to the appropriate backend and return a normalized response.

    When the selected ``MODEL`` names a Claude model, this function forwards
    messages directly to the Anthropic API using the ``/v1/messages`` endpoint
    and includes the standard headers for the date-versioned Anthropic API
   【911796291458355†L45-L49】.  The response from Anthropic is already in the
    internal format (with ``content`` blocks).  For OpenAI models the
    conversation history and tool definitions are converted to the Chat
    Completions schema; an API request is issued and the response is
    converted back into the internal block format.
    """
    use_anthropic = MODEL.lower().startswith("claude") or MODEL.lower().startswith("anthropic")
    if use_anthropic:
        request = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=json.dumps(
                {
                    "model": MODEL,
                    "max_tokens": 8192,
                    "system": system_prompt,
                    "messages": messages,
                    "tools": make_schema(),
                }
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                "anthropic-version": "2023-06-01",
            },
        )
        resp = urllib.request.urlopen(request)
        return json.loads(resp.read())
    # Otherwise use OpenAI
    # Convert messages and tools
    openai_messages = convert_messages_to_openai(messages)
    openai_tools = make_openai_tools()
    # Determine the endpoint: codex models only live behind the responses API
    if "codex" in MODEL.lower():
        url = OPENAI_RESPONSES_URL
    else:
        url = OPENAI_CHAT_URL
    body = {
        "model": MODEL,
        "messages": openai_messages,
        "tools": openai_tools,
        # Use a generous token limit to mirror Anthropic's default
        "max_tokens": 8192,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
        },
    )
    resp = urllib.request.urlopen(request)
    data: Dict[str, Any] = json.loads(resp.read())
    # Extract the assistant message from the first choice
    choice = data.get("choices", [{}])[0].get("message", {})
    content_blocks: List[Dict[str, Any]] = []
    # Include plain text if present
    if choice.get("content"):
        content_blocks.append({"type": "text", "text": choice["content"]})
    # Process tool calls
    for call in choice.get("tool_calls", []) or []:
        args = {}
        try:
            args = json.loads(call.get("function", {}).get("arguments", "{}"))
        except Exception:
            pass
        content_blocks.append(
            {
                "type": "tool_use",
                "id": call.get("id"),
                "name": call.get("function", {}).get("name"),
                "input": args,
            }
        )
    return {"content": content_blocks}


def separator() -> str:
    width = min(os.get_terminal_size().columns, 80)
    return f"{DIM}{'─' * width}{RESET}"


def render_markdown(text: str) -> str:
    """Render bold text in the terminal by replacing **text** markers."""
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def main() -> None:
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} | {os.getcwd()}{RESET}\n")
    messages: List[Dict[str, Any]] = []
    system_prompt = f"Concise coding assistant. cwd: {os.getcwd()}"
    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue
            messages.append({"role": "user", "content": user_input})
            # Agentic loop: keep calling API until no more tool calls
            while True:
                response = call_api(messages, system_prompt)
                content_blocks = response.get("content", [])
                tool_results: List[Dict[str, Any]] = []
                for block in content_blocks:
                    if block["type"] == "text":
                        print(f"\n{CYAN}⏺{RESET} {render_markdown(block['text'])}")
                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_args = block["input"]
                        # Show a preview of the first argument value
                        arg_preview = str(list(tool_args.values())[0])[:50] if tool_args else ""
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )
                        result = run_tool(tool_name, tool_args)
                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f" {DIM}⎿ {preview}{RESET}")
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": result,
                            }
                        )
                # Record the assistant message
                messages.append({"role": "assistant", "content": content_blocks})
                # If no tools were invoked, break
                if not tool_results:
                    break
                # Append tool results for the next request
                messages.append({"role": "user", "content": tool_results})
            print()
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
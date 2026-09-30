# WayKit (formerly Lectic) as an MCP server

`scripts/waykit_mcp.py` and `scripts/lectic_mcp.py` expose the compiler over the Model Context Protocol (JSON-RPC over stdio). Any MCP client can then operate WayKit through tools: Claude Code, Codex and others reach the same WayKit home without an installed skill and without touching its files directly. Reasoning still belongs to the client; the server owns storage, identity, validation and provenance.

All tools are available with both the modern `waykit_*` prefix and the legacy `lectic_*` prefix (e.g. `waykit_home` and `lectic_home`).

It requires Python 3.10+ and the package runtime dependencies (`cryptography`, plus `tomli` on Python 3.10). Install WayKit as a package before launching the server.

The intelligent context tools are `waykit_knowledge`, `waykit_explain`, `waykit_context`, and `waykit_import_plan` (also callable as `lectic_knowledge`, `lectic_explain`, etc.). They infer knowledge roles and relationships, compose only the evidence-backed units relevant to the current task, preserve current task details without saving them as permanent knowledge, and explain gaps without blocking the assistant. Their results are plain JSON and Markdown so every model provider can use them.

## Connect a client

The short way:

```bash
pip install waykit
waykit setup
```

Legacy `pip install lectic` and `lectic setup` remain supported aliases.

`waykit setup` registers the server with Claude Code (through `claude mcp add`, or its user config when the CLI is absent) and Codex (`~/.codex/config.toml`), runs a real handshake to prove the server starts, and offers to add YouTube support. It is safe to repeat. `waykit status` shows what is connected. The server is launched as `python -m waykit.cli serve` with the interpreter pip used, so nothing depends on PATH.

For ChatGPT, Claude on the web, Gemini, your phone or another computer, `waykit share` serves the same server over Streamable HTTP behind one private link; see [Anywhere](CLOUD.md).

The manual way, from a checkout, with a Python 3.10+ interpreter path:

**Claude Code** (once, from any folder):

```bash
claude mcp add --scope user waykit -- python /path/to/waykit/scripts/waykit_mcp.py
```

Or per project in `.mcp.json`:

```json
{"mcpServers": {"waykit": {"command": "python", "args": ["/path/to/waykit/scripts/waykit_mcp.py"]}}}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.waykit]
command = "python"
args = ["/path/to/waykit/scripts/waykit_mcp.py"]
```

The server treats its working directory as the user's project; every tool also accepts an explicit `project`. Set `WAYKIT_HOME` (or `LECTIC_HOME`) in the client's environment to point all of them at one home (see [installation](INSTALLATION.md#where-knowledge-is-stored)).

**Hosted assistants** (ChatGPT, Claude on the web, Gemini) need an HTTPS address rather than a local process: `waykit share`, or the always-on container. [Anywhere →](CLOUD.md)

Check the server independently with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector --cli python /path/to/waykit/scripts/waykit_mcp.py --method tools/list
```

## Transports

The same `Server` answers over two transports. **stdio** (`waykit serve`): one JSON-RPC message per line, what `waykit setup` registers. **Streamable HTTP** (`waykit serve --http`, `waykit share`): `POST /mcp` with JSON-RPC, plain JSON responses, `202` for notifications, `405` on `GET` because the server never opens a stream to the client. The secret travels in the path (`/t/<secret>/mcp`, what hosted connectors accept without OAuth) or as `Authorization: Bearer <secret>`. A browser page from another origin cannot drive a server bound to this machine. Tool calls are serialized: the coordinators expect one writer per home. `POST /t/<secret>/capture` accepts a phone's share, and `GET`/`POST /t/<secret>/home` move a whole home to or from the server ([moving your knowledge](CLOUD.md#moving-your-knowledge)). A server serves one home, fixed when it starts. Both transports are verified against the official MCP Inspector.

## Tools

All tools are callable with `waykit_*` or legacy `lectic_*` prefix:

| Tool | Purpose |
| --- | --- |
| `waykit_home` (`lectic_home`) | Where knowledge is stored for this project and why |
| `waykit_library` (`lectic_library`) | Read-only inventory: collections, ready methods, earlier results, possible builds |
| `waykit_work` (`lectic_work`) | Goal coordinator: save, prepare, apply to a brief, export, compare, archive |
| `waykit_map` (`lectic_map`) | Capability Maps: discover, list, inspect, compare, select |
| `waykit_guide` (`lectic_guide`) | Grounded next-use suggestions: prepare, save, show, select |
| `waykit_capture` (`lectic_capture`) | Inbox: import a synced folder, list, show, memberships, notes, process, trace |
| `waykit_capture_save` (`lectic_capture_save`) | Save a link, pasted text or files shared right now; storage only. Returns `decision` (`explicit` / `auto_filed` / `needs_clarification` / `inbox_fallback`), a single `question` when one is warranted, and a `source` object saying whether the item's content is retrievable (YouTube captions) or kept as a reference only (Instagram, TikTok, most web links) |
| `waykit_collection_candidates` (`lectic_collection_candidates`) | Intelligent candidate collection suggestions for incoming source material |
| `waykit_compile` (`lectic_compile`) | Legacy numbered-capability coordinator |
| `waykit_pack` (`lectic_pack`) | One shareable `.waykit` / `.lectic` file carrying a collection's knowledge |
| `waykit_install` (`lectic_install`) | Install or inspect a pack from a file or https link |
| `waykit_verify` (`lectic_verify`) | Evidence linkage health and source verification for a collection |
| `waykit_identity` (`lectic_identity`) | Local pack-signing identity management (show or set) |
| `waykit_backup` (`lectic_backup`) | Write the whole home to one archive file |
| `waykit_transfer` (`lectic_transfer`) | push, pull or restore a home |
| `waykit_validate_build` (`lectic_validate_build`) | Deterministic build verification |
| `waykit_read` (`lectic_read`) | Read a prompt, schema, source, knowledge file, brief or draft the workflow named |
| `waykit_write_json` (`lectic_write_json`) | Save a record the workflow asked for, validated against its schema |

Prompts and schemas are published as both `waykit://` and legacy `lectic://` resources (`waykit://prompts/NAME.md`, `lectic://prompts/NAME.md`, etc.), so a client can load the reasoning contract without a checkout.

## How a workflow runs over tools

Workflow tools return a `phase`. When the response carries `agent_task`, it is work for the client: read the named prompt with `waykit_read` (or `lectic_read`), reason, save the requested record with `waykit_write_json` (or `lectic_write_json`) at the path the task names, then call the same workflow tool again. This is the same state machine the installed skill drives with the CLI; only the transport changed.

`waykit_write_json` (or `lectic_write_json`) is the single door for records the client produces. It admits exactly the kinds a workflow asks for, and validates each before it lands:

| Location | Kind | Validation |
| --- | --- | --- |
| `RUN/units/SOURCE_ID.json` | extraction checkpoint | extraction schema; corpus and source identity; every quote located in the source segments |
| `.../requests/.../coverage.json`, `method.json`, `result.json` | goal drafts | coverage-assessment, goal-method, outcome or work-result schemas |
| `RUN/capabilities.json`, `RUN/discovery-assessment.json` | legacy discovery | bound to the run's IR |
| `.../maps/drafts/*.json` | Capability Map draft | capability-map-draft schema |
| `HOME/use-guides/drafts/*.json` | next-use guide draft | use-guide schema |
| `HOME/inbox/*.json` | brief | brief schema |
| `.../evaluation/*.json` | evaluation tasks, rubric, responses | JSON only; the evaluation harness validates the pair |

Everything else is refused: published builds, knowledge history, sources, raw bytes, capture records and state, indexes, and any path outside the WayKit home. A rejection names the rule, so the client fixes the record rather than working around it. Reads are limited to the home and the installed skill.

## WayKit Cloud Remote MCP (Goal-Oriented Chat Tools)

When connected to an authenticated WayKit Cloud instance (`waykit cloud serve`), assistants interact through high-level conversational tools (`scripts/cloud_mcp.py`):

| Tool | Purpose |
| --- | --- |
| `save_knowledge` | Save URLs, shared text, or snippets into user collections or inbox. Pure storage; zero background extraction. |
| `learn_from_source` | Extract principles and methods from a saved capture, text, or collection, preserving exact quotes as evidence and labeling status (`observed` vs `inferred`). |
| `organize_knowledge` | Infer, link, unlink, or explain typed pack relationships (`specializes`, `personal_preference_relevant_to`, `related_to`). |
| `get_relevant_context` | Assemble relevant knowledge units and identify knowledge gaps for the user's active task. |
| `apply_knowledge` | Apply knowledge to evaluate, review, or answer a task, citing verifiable source quotes. |
| `search_knowledge` | Search across all collections and units in the user's private library. |
| `export_library` | Generate a portable `.waykit-home` (or `.lectic-home`) zip archive for backup or restore into local WayKit. |

These tools require no compiler phase knowledge from the user or assistant and are strictly authenticated against the account associated with the bearer token or OAuth authorization code.

## What this establishes, and what it does not

Because every client-produced record now passes through one validated door, the store beneath it can change without the client noticing: a remote store implementing the same seam is the next step, and index files can replace directory listing once no client writes files directly. Semantic quality is unchanged by the transport: the server verifies structure, identity and evidence location, not whether an interpretation is right. Human review and evaluation remain part of quality assurance.

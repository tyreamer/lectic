# Lectic as an MCP server

`scripts/lectic_mcp.py` exposes the compiler over the Model Context Protocol (JSON-RPC over stdio). Any MCP client can then operate Lectic through tools: Claude Code, Codex and others reach the same Lectic home without an installed skill and without touching its files directly. Reasoning still belongs to the client; the server owns storage, identity, validation and provenance.

It is stdlib-only Python 3.10+, like the rest of the compiler. There is nothing to install beyond a checkout (or an installed skill, which contains the same `scripts/` folder).

## Connect a client

The short way:

```bash
pip install lectic
lectic setup
```

`lectic setup` registers the server with Claude Code (through `claude mcp add`, or its user config when the CLI is absent) and Codex (`~/.codex/config.toml`), runs a real handshake to prove the server starts, and offers to add YouTube support. It is safe to repeat. `lectic status` shows what is connected. The server is launched as `python -m lectic.cli serve` with the interpreter pip used, so nothing depends on PATH.

For ChatGPT, Claude on the web, Gemini, your phone or another computer, `lectic share` serves the same server over Streamable HTTP behind one private link; see [Anywhere](CLOUD.md).

The manual way, from a checkout, with a Python 3.10+ interpreter path:

**Claude Code** (once, from any folder):

```bash
claude mcp add --scope user lectic -- python /path/to/lectic/scripts/lectic_mcp.py
```

Or per project in `.mcp.json`:

```json
{"mcpServers": {"lectic": {"command": "python", "args": ["/path/to/lectic/scripts/lectic_mcp.py"]}}}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.lectic]
command = "python"
args = ["/path/to/lectic/scripts/lectic_mcp.py"]
```

The server treats its working directory as the user's project; every tool also accepts an explicit `project`. Set `LECTIC_HOME` in the client's environment to point all of them at one home (see [installation](INSTALLATION.md#where-knowledge-is-stored)).

**Hosted assistants** (ChatGPT, Claude on the web, Gemini) need an HTTPS address rather than a local process: `lectic share`, or the always-on container. [Anywhere →](CLOUD.md)

Check the server independently with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector --cli python /path/to/lectic/scripts/lectic_mcp.py --method tools/list
```

## Transports

The same `Server` answers over two transports. **stdio** (`lectic serve`): one JSON-RPC message per line, what `lectic setup` registers. **Streamable HTTP** (`lectic serve --http`, `lectic share`): `POST /mcp` with JSON-RPC, plain JSON responses, `202` for notifications, `405` on `GET` because the server never opens a stream to the client. The secret travels in the path (`/t/<secret>/mcp`, what hosted connectors accept without OAuth) or as `Authorization: Bearer <secret>`. A browser page from another origin cannot drive a server bound to this machine. Tool calls are serialized: the coordinators expect one writer per home. `POST /t/<secret>/capture` accepts a phone's share, and `GET`/`POST /t/<secret>/home` move a whole home to or from the server ([moving your knowledge](CLOUD.md#moving-your-knowledge)). A server serves one home, fixed when it starts. Both transports are verified against the official MCP Inspector.

## Tools

| Tool | Purpose |
| --- | --- |
| `lectic_home` | Where knowledge is stored for this project and why |
| `lectic_library` | Read-only inventory: collections, ready methods, earlier results, possible builds |
| `lectic_work` | Goal coordinator: save, prepare, apply to a brief, export, compare, archive |
| `lectic_map` | Capability Maps: discover, list, inspect, compare, select |
| `lectic_guide` | Grounded next-use suggestions: prepare, save, show, select |
| `lectic_capture` | Inbox: import a synced folder, list, show, memberships, notes, process, trace |
| `lectic_capture_save` | Save a link, pasted text or files shared right now; storage only |
| `lectic_collection_candidates` | Intelligent candidate collection suggestions for incoming source material |
| `lectic_compile` | Legacy numbered-capability coordinator |
| `lectic_pack` | One shareable `.lectic` file carrying a collection's knowledge |
| `lectic_install` | Install or inspect a pack from a file or https link |
| `lectic_verify` | Evidence linkage health and source verification for a collection |
| `lectic_identity` | Local pack-signing identity management (show or set) |
| `lectic_backup` | Write the whole home to one archive file |
| `lectic_transfer` | push, pull or restore a home |
| `lectic_validate_build` | Deterministic build verification |
| `lectic_read` | Read a prompt, schema, source, knowledge file, brief or draft the workflow named |
| `lectic_write_json` | Save a record the workflow asked for, validated against its schema |

Prompts and schemas are also published as resources (`lectic://prompts/NAME.md`, `lectic://schemas/NAME.schema.json`, `lectic://skill/SKILL.md`), so a client can load the reasoning contract without a checkout.

## How a workflow runs over tools

Workflow tools return a `phase`. When the response carries `agent_task`, it is work for the client: read the named prompt with `lectic_read`, reason, save the requested record with `lectic_write_json` at the path the task names, then call the same workflow tool again. This is the same state machine the installed skill drives with the CLI; only the transport changed.

`lectic_write_json` is the single door for records the client produces. It admits exactly the kinds a workflow asks for, and validates each before it lands:

| Location | Kind | Validation |
| --- | --- | --- |
| `RUN/units/SOURCE_ID.json` | extraction checkpoint | extraction schema; corpus and source identity; every quote located in the source segments |
| `.../requests/.../coverage.json`, `method.json`, `result.json` | goal drafts | coverage-assessment, goal-method, outcome or work-result schemas |
| `RUN/capabilities.json`, `RUN/discovery-assessment.json` | legacy discovery | bound to the run's IR |
| `.../maps/drafts/*.json` | Capability Map draft | capability-map-draft schema |
| `HOME/use-guides/drafts/*.json` | next-use guide draft | use-guide schema |
| `HOME/inbox/*.json` | brief | brief schema |
| `.../evaluation/*.json` | evaluation tasks, rubric, responses | JSON only; the evaluation harness validates the pair |

Everything else is refused: published builds, knowledge history, sources, raw bytes, capture records and state, indexes, and any path outside the Lectic home. A rejection names the rule, so the client fixes the record rather than working around it. Reads are limited to the home and the installed skill.

## What this establishes, and what it does not

Because every client-produced record now passes through one validated door, the store beneath it can change without the client noticing: a remote store implementing the same seam is the next step, and index files can replace directory listing once no client writes files directly. Semantic quality is unchanged by the transport: the server verifies structure, identity and evidence location, not whether an interpretation is right. Human review and evaluation remain part of quality assurance.

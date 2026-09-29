# Reach your knowledge from anywhere

WayKit keeps one home per user. `waykit setup` (or `lectic setup`) connects the assistants on the same machine to it. This guide is for everything else: ChatGPT, Claude on the web, Gemini, your phone, or a second computer.

All of them need the same thing: **one link**. The link is an HTTPS address ending in `/t/<secret>/mcp`. Hosted assistants add it as a connector; your phone posts captures to its `/capture` sibling; Claude Code and Codex on another machine take it with `waykit connect`. The secret is made once per home, never typed, and is the whole of the link's security: anyone holding it can read and change your knowledge, so treat it like a password. `waykit share --new-link` retires it.

There is no separate cloud copy of your knowledge to keep in sync. Wherever the server runs, that home is the knowledge.

## Option 1: share this machine

```bash
waykit share
```

Serves over HTTP on this machine and opens a Cloudflare Tunnel to it, then prints the link and where to paste it. Nothing is exposed except the two authenticated endpoints; stop it with Ctrl+C. It needs `cloudflared` once (`winget install Cloudflare.cloudflared` on Windows, `brew install cloudflared` on macOS); `waykit share` tells you if it is missing.

A quick tunnel gets a new address each run, so connectors need re-adding after a restart. For a permanent address on your own domain, create a [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) once, then:

```bash
waykit share --tunnel NAME --hostname https://waykit.yourdomain.com
```

Already have a public address for this machine (Tailscale Funnel, ngrok, a reverse proxy)? Point it at `127.0.0.1:8787` and run `waykit share --public https://that-address`.

## Moving your knowledge

Wherever the server runs, that home *is* the knowledge — so the only question is getting yours there.

```bash
waykit backup                      # everything in one archive file
waykit restore FILE                # merge it into this machine's knowledge
waykit push  https://…/t/SECRET/mcp   # send this home to a WayKit running elsewhere
waykit pull  https://…/t/SECRET/mcp   # bring that one's knowledge here
```

All four move the same archive: every collection, source, capture, map and build, minus the things that belong to one machine (its secret, its live share link, its per-project session pointers). Because sources are content-addressed and collections carry stable IDs, a merge **adds what is missing and never overwrites**:

- a collection that is already there, byte for byte, is recognised and skipped;
- a collection that exists on both sides and differs is reported as diverged and both copies are left exactly as they were;
- an incoming collection whose name is taken lands beside the local one as `Name (2)`;
- sources you already have are not re-sent or re-stored.

Repeating a restore or push is therefore safe. The report names every collection added, already present, or kept apart, and anything that failed to validate afterwards.

A practical first move onto a hosted WayKit:

```bash
waykit push https://your-host/t/SECRET/mcp
waykit connect https://your-host/t/SECRET/mcp
```

Back up on a schedule once the hosted home is the one you rely on — `waykit backup --out /path/to/backups` writes a timestamped archive, and nothing but the file is needed to rebuild.

## Option 2: always on

When the laptop should not be the server, run the same code in a container on any host with a persistent volume (Fly.io, Railway, a VPS with Docker):

```bash
docker build -t waykit .
docker run -d --name waykit -p 8787:8787 -v waykit-data:/data -e WAYKIT_TOKEN=<a long random secret> waykit
```

Put HTTPS in front of it (the host's own proxy, or a Cloudflare Tunnel on the box) and the link is `https://your-host/t/<secret>/mcp`. `WAYKIT_PUBLIC_URL=https://your-host` makes the container print the finished link at start. Knowledge lives on the volume; back it up like any personal data.

Move your existing knowledge onto it with `waykit push <link>` (above). Then, on each computer where you use Claude Code or Codex:

```bash
waykit connect https://your-host/t/<secret>/mcp
```

`waykit setup` switches a machine back to its own local knowledge at any time.

YouTube retrieval from a datacenter is often blocked by YouTube. Connecting a home computer to the hosted server does not move retrieval: tools still run on the server. If captions fail there, process them in a local WayKit home on a permitted network, then transfer the resulting knowledge with `waykit push`. Existing collections that differ remain separate; inspect the merge report. The server can also use an explicitly configured permitted proxy.

## Where to paste the link

| Assistant | Where |
| --- | --- |
| ChatGPT | Settings → Apps & Connectors → Create. Authentication: none. Developer mode may need enabling. |
| Claude (web/desktop) | Settings → Connectors → Add custom connector. |
| Gemini CLI | `gemini mcp add --transport http waykit <link>` |
| Claude Code, Codex | `waykit connect <link>` |
| Any MCP client | Streamable HTTP at the link; or `Authorization: Bearer <secret>` against `/mcp`. |

Menus move; the constant is a Streamable HTTP MCP server that needs no OAuth because the secret is in the link.

## Your phone

Captures no longer need a synced folder. In Shortcuts, make a Share Sheet shortcut with two actions:

1. **Get Contents of URL** — URL `https://your-host/t/<secret>/capture`, Method POST, Request Body: File, with the Shortcut Input.
2. **Show Result** (optional): the reply says what was saved.

Send JSON instead (`{"value": "...", "note": "why I saved it", "collection": "Sales"}`) to attach a reason or file it straight into a collection. Saving never retrieves, extracts or builds anything; the link waits in the Inbox until a use needs it. The [synced-folder Shortcut](iphone-shortcut.md) still works for phones that cannot reach the server.

## Option 3: WayKit Cloud (multi-user account & library service)

When you want a hosted service supporting multiple users, account authorization, and OAuth 2.0 connection from ChatGPT or Claude:

```bash
waykit cloud serve --host 0.0.0.0 --port 8787 --root /data/cloud
```

### Server endpoints

- **OAuth 2.0 Discovery**: `GET /.well-known/oauth-authorization-server`
- **OAuth Consent**: `GET /oauth/authorize` & `POST /oauth/authorize`
- **OAuth Token**: `POST /oauth/token` (Authorization Code with PKCE `S256`)
- **Token Revocation**: `POST /oauth/revoke`
- **Remote MCP**: `POST /mcp` (Bearer token) or `POST /t/<token>/mcp`
- **Web Dashboard**: `GET /account/dashboard` (Inspect tokens, revoking access, downloading library archive)
- **Direct Phone Capture**: `POST /t/<token>/capture`

### User and token management

```bash
waykit cloud create-user user@example.com --name "Alice"
waykit cloud token user@example.com --client "ChatGPT Mobile"
waykit cloud list-users
waykit cloud export user@example.com --out alice-backup.waykit-home
```

### Chat tools available in conversation

Once connected to WayKit Cloud, assistants have access to goal-oriented tools that work without technical terminology:

- `save_knowledge`: Store links, notes, or text directly into private collections or inbox. Never triggers premature extraction or paid model execution.
- `learn_from_source`: Synthesizes reusable principles and rules, keeping exact quotes as evidence and labeling epistemic status (`observed` vs `inferred`).
- `organize_knowledge`: Connects packs with typed relationships (`specializes`, `personal_preference_relevant_to`, `related_to`).
- `get_relevant_context`: Dynamically selects relevant authorized knowledge units and notes gaps for the active task.
- `apply_knowledge`: Applies relevant knowledge to evaluate, review, or generate solutions citing verifiable sources.
- `search_knowledge`: Searches across the user's private library.
- `export_library`: Exports the entire private library as a standard `.waykit-home` (or legacy `.lectic-home`) archive.

### Exporting and restoring to local WayKit

You can download your entire library at any time from `/account/export`, via the `export_library` chat tool, or with `waykit cloud export`:

```bash
waykit restore alice-backup.waykit-home
```

All collections, sources, and knowledge units are merged into your local WayKit home with zero data loss. Legacy `.lectic-home` archives and commands are fully supported.

## What this is, and is not

Local WayKit and `waykit share` are single-user by design (one home, zero cloud accounts). `waykit cloud` provides the multi-tenant account and private library foundation with OAuth 2.0 for hosted deployments.

Billing, commercial marketplaces, team collaboration, and automated bidirectional sync remain deferred. Knowledge portability is guaranteed through standard `.waykit-home` / `.lectic-home` archives. Legacy `lectic` command invocations remain fully supported.


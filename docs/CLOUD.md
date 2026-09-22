# Reach your knowledge from anywhere

Lectic keeps one home per user. `lectic setup` connects the assistants on the same machine to it. This guide is for everything else: ChatGPT, Claude on the web, Gemini, your phone, or a second computer.

All of them need the same thing: **one link**. The link is an HTTPS address ending in `/t/<secret>/mcp`. Hosted assistants add it as a connector; your phone posts captures to its `/capture` sibling; Claude Code and Codex on another machine take it with `lectic connect`. The secret is made once per home, never typed, and is the whole of the link's security: anyone holding it can read and change your knowledge, so treat it like a password. `lectic share --new-link` retires it.

There is no separate cloud copy of your knowledge to keep in sync. Wherever the server runs, that home is the knowledge.

## Option 1: share this machine

```bash
lectic share
```

Serves over HTTP on this machine and opens a Cloudflare Tunnel to it, then prints the link and where to paste it. Nothing is exposed except the two authenticated endpoints; stop it with Ctrl+C. It needs `cloudflared` once (`winget install Cloudflare.cloudflared` on Windows, `brew install cloudflared` on macOS); `lectic share` tells you if it is missing.

A quick tunnel gets a new address each run, so connectors need re-adding after a restart. For a permanent address on your own domain, create a [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) once, then:

```bash
lectic share --tunnel NAME --hostname https://lectic.yourdomain.com
```

Already have a public address for this machine (Tailscale Funnel, ngrok, a reverse proxy)? Point it at `127.0.0.1:8787` and run `lectic share --public https://that-address`.

## Moving your knowledge

Wherever the server runs, that home *is* the knowledge — so the only question is getting yours there.

```bash
lectic backup                      # everything in one archive file
lectic restore FILE                # merge it into this machine's knowledge
lectic push  https://…/t/SECRET/mcp   # send this home to a Lectic running elsewhere
lectic pull  https://…/t/SECRET/mcp   # bring that one's knowledge here
```

All four move the same archive: every collection, source, capture, map and build, minus the things that belong to one machine (its secret, its live share link, its per-project session pointers). Because sources are content-addressed and collections carry stable IDs, a merge **adds what is missing and never overwrites**:

- a collection that is already there, byte for byte, is recognised and skipped;
- a collection that exists on both sides and differs is reported as diverged and both copies are left exactly as they were;
- an incoming collection whose name is taken lands beside the local one as `Name (2)`;
- sources you already have are not re-sent or re-stored.

Repeating a restore or push is therefore safe. The report names every collection added, already present, or kept apart, and anything that failed to validate afterwards.

A practical first move onto a hosted Lectic:

```bash
lectic push https://your-host/t/SECRET/mcp
lectic connect https://your-host/t/SECRET/mcp
```

Back up on a schedule once the hosted home is the one you rely on — `lectic backup --out /path/to/backups` writes a timestamped archive, and nothing but the file is needed to rebuild.

## Option 2: always on

When the laptop should not be the server, run the same code in a container on any host with a persistent volume (Fly.io, Railway, a VPS with Docker):

```bash
docker build -t lectic .
docker run -d --name lectic -p 8787:8787 -v lectic-data:/data -e LECTIC_TOKEN=<a long random secret> lectic
```

Put HTTPS in front of it (the host's own proxy, or a Cloudflare Tunnel on the box) and the link is `https://your-host/t/<secret>/mcp`. `LECTIC_PUBLIC_URL=https://your-host` makes the container print the finished link at start. Knowledge lives on the volume; back it up like any personal data.

Move your existing knowledge onto it with `lectic push <link>` (above). Then, on each computer where you use Claude Code or Codex:

```bash
lectic connect https://your-host/t/<secret>/mcp
```

`lectic setup` switches a machine back to its own local knowledge at any time.

YouTube retrieval from a datacenter is often blocked by YouTube. If captions fail on the hosted server, save the link there and process the collection once from a machine on a home connection with `lectic connect` pointed at the server; the retrieved captions are cached in the home.

## Where to paste the link

| Assistant | Where |
| --- | --- |
| ChatGPT | Settings → Apps & Connectors → Create. Authentication: none. Developer mode may need enabling. |
| Claude (web/desktop) | Settings → Connectors → Add custom connector. |
| Gemini CLI | `gemini mcp add --transport http lectic <link>` |
| Claude Code, Codex | `lectic connect <link>` |
| Any MCP client | Streamable HTTP at the link; or `Authorization: Bearer <secret>` against `/mcp`. |

Menus move; the constant is a Streamable HTTP MCP server that needs no OAuth because the secret is in the link.

## Your phone

Captures no longer need a synced folder. In Shortcuts, make a Share Sheet shortcut with two actions:

1. **Get Contents of URL** — URL `https://your-host/t/<secret>/capture`, Method POST, Request Body: File, with the Shortcut Input.
2. **Show Result** (optional): the reply says what was saved.

Send JSON instead (`{"value": "...", "note": "why I saved it", "collection": "Sales"}`) to attach a reason or file it straight into a collection. Saving never retrieves, extracts or builds anything; the link waits in the Inbox until a use needs it. The [synced-folder Shortcut](iphone-shortcut.md) still works for phones that cannot reach the server.

## What this is, and is not

The server is single-user by design: one home, one secret, no accounts. It is the same stdlib Python that runs locally, with Streamable HTTP added, verified against the MCP Inspector. It does not add a hosted database, billing or a marketplace, and it does not change what Lectic establishes: structure, identity and evidence are verified by the server; whether an interpretation is right still needs a person.

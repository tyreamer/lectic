# Knowledge packs

A pack is one file, `<name>.lectic`, that carries a collection's compiled expertise to someone else. They install it and every assistant they have connected can apply it, from any project, with no re-upload and no shared project files.

```bash
lectic pack "FC 27"                 # -> fc-27.lectic
lectic install fc-27.lectic         # or: lectic install https://…/fc-27.lectic
```

Or in conversation: “Pack my FC 27 collection so I can share it” / “Install this pack: <link>”. `lectic install --inspect <file>` shows what a pack contains before installing anything.

## What travels

| In the pack | Why |
| --- | --- |
| Knowledge: every unit with its evidence citations, the per-source checkpoints, the author's reconciliation receipt | The compiled expertise itself, in the same records the compiler validates |
| Evidence excerpts | The exact passages the knowledge cites, readable without the sources |
| The latest Capability Map and built methods | What the collection can do, as readable records |
| A rendered `README.md` | The pack explains itself to a person with no Lectic |
| A manifest with a hash of every file | Nothing can be altered on the way |

## What does not travel: the sources

By default a pack carries source **links and hashes, not source text**. Installing it retrieves each source again on the installer's own network (YouTube captions through their `yt-dlp`) and checks the bytes against the pack's hashes. The knowledge is then validated against *their* copy exactly as it was against yours. Nothing of the original material is redistributed, which is what makes a pack safe to post publicly.

`lectic pack NAME --include-sources` bundles full source text. Use it for material you own or may share, such as your own transcripts and notes; local files have no link to retrieve from, so a links-only pack of them cannot be installed.

## What the installer sees

Install reports one of two things:

- **verified** — every source was obtained and matched, every unit validated, the author's cross-source review carries over, and the installed knowledge hash equals the pack's. Goal work can start immediately.
- **partial: N of M sources, X of Y units** — a source could not be obtained (no link, no retriever, network blocked) or its content changed since it was packed (YouTube regenerates auto-captions). Its units drop, along with anything that leaned on them, and the report names each source and reason. The remaining knowledge is installed; reconciliation is asked for before goal work, because the author's review no longer covers exactly what is present.

If no source can be obtained, nothing is installed and the reason is spelled out. A pack that was altered, or that contains unsafe paths, is refused before anything is read from it.

Installing the same pack twice keeps both copies apart (`FC 27`, `FC 27 (2)`); `--name` (or `--as`) picks a name. The library shows an installed collection's pack origin and its readable methods; `lectic status` counts it like any other collection.

## Team distribution

A team pack carries complete standards, rules, and procedures bundled with sources and explicit install instructions for Claude Code, Codex, and ChatGPT:

```bash
lectic pack "Engineering Standards" --team --version 2.1.0
```

- **Sources bundled automatically**: No re-fetch required; your team owns and controls the material.
- **Distribution metadata**: Contains `scope: team`, `install_name: engineering-standards`, and `pinned_version`.
- **`INSTALL.md` generated**: Clear, single-command setup instructions embedded right in the pack.

New team members install with predictable naming and version pinning:

```bash
lectic install https://.../engineering-standards.lectic --as engineering --pin
```

## Version pinning & updates

Team standards evolve. Pinning locks an installed collection to the pack's version:

- `lectic install FILE|URL --pin`: Records pinned status and origin in collection metadata.
- `lectic status`: Shows which collections are pinned and their versions (`engineering v2.1.0 [pinned]`).
- `lectic update NAME`: Checks the pack's origin URL for a newer release and upgrades in-place:
  ```text
  Updated engineering from 2.0.0 to 2.1.0 — 3 new conventions added, 1 modified
  ```

## Publishing to team hosts

Publish a compiled pack directly to GitHub Releases, an S3 / R2 presigned URL, or generic HTTP PUT host:

```bash
lectic publish "Engineering Standards" --to https://github.com/myorg/standards/releases/tag/v2.1.0
# Or with a Slack webhook notification:
lectic publish "Engineering Standards" --to https://github.com/myorg/standards --webhook https://hooks.slack.com/services/...
```

Output:
```text
Published Engineering Standards v2.1.0. Team install: lectic install https://github.com/myorg/standards/releases/download/v2.1.0/engineering-standards.lectic --as engineering-standards
```

## Expertise Marketplace & Registry

The Lectic registry allows discovering, inspecting, and installing community-contributed and team knowledge packs without needing to manage URLs manually.

```bash
# Search for verified packs by keyword or category tag
lectic search engineering
lectic search --tag architecture

# Preview pack evidence guarantee, methods, and README before installing
lectic inspect registry:distributed-systems-adr

# Install directly from the registry with version pinning
lectic install registry:distributed-systems-adr --as distributed-systems --pin
```

Browse the web marketplace at [tyreamer.github.io/lectic/registry.html](https://tyreamer.github.io/lectic/registry.html).

### Publishing to the community registry

To submit your pack to the community marketplace:
1. Ensure your signing identity is set: `lectic identity set "Your Name" --contact you@domain.com`
2. Pack your collection: `lectic pack NAME --team`
3. Generate the schema-compliant registry entry: `lectic publish NAME --to <download-url> --registry [--tags tag1,tag2]`
4. Open a Pull Request adding the printed JSON block to `registry/index.json` in [tyreamer/lectic](https://github.com/tyreamer/lectic).

## Sharing

The file goes wherever files go: a GitHub release, a gist, a bucket, a message. Recipients need Lectic (`pip install lectic`); the pack's own README and INSTALL.md tell them so.

Packs are content-addressed: the same knowledge over the same sources produces the same `pack_id`, so two people can tell they hold the same thing.

## What a pack does not do

It does not make knowledge true. The installer's Lectic verifies structure, identity and evidence location against their copy of the sources; whether the author's interpretation is right is the same question it always was. Maps and methods arrive as readable records, not as live builds, because builds bind to the collection that made them; the installer's assistant regenerates a map or builds a method from the installed knowledge when asked.

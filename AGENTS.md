# Setting up Lectic for someone (instructions for an AI assistant)

If a person pointed you at this repository and asked you to set it up, do it for them. They should not have to know what Python or pip is, choose an interpreter, edit a config file, or run a command themselves. Do the work, check that it worked, and tell them the one thing they need to do next.

## 1. Find a Python 3.10 or newer

Try in order and use the first that reports 3.10+: `python3`, `python`, `py -3`, then common install locations. On Windows `python` is often an older Anaconda build.

```
<candidate> -c "import sys; print(sys.version)"
```

**If installing later fails with `No matching distribution found for lectic`, that is the wrong interpreter, not a missing package.** Lectic requires 3.10+; older ones are told there is no such release. Find a newer interpreter, or install one (`winget install Python.Python.3.12` on Windows, `brew install python@3.12` on macOS) with the person's approval, then continue.

## 2. Install

```
<python> -m pip install --upgrade lectic
```

Use `python -m pip`, not a bare `pip`, so it installs into the interpreter you just chose.

## 3. Connect their assistants

```
<python> -m lectic.cli setup --yes
```

Always invoke it as `<python> -m lectic.cli`. A bare `lectic` command may not be on PATH depending on how their Python was installed; the module form always works and the configs it writes are PATH-independent.

This finds Claude Code and Codex, writes their MCP configuration, verifies the server actually starts, and reports what it did. It is safe to run again. Read its output: any line that is not `connected` tells you what happened.

To add YouTube support without the interactive prompt: `<python> -m pip install yt-dlp`.

## 4. Check it

```
<python> -m lectic.cli status
```

`Server ok` plus at least one `connected` assistant means setup succeeded. If something is wrong, that output names it; fix it rather than reporting success.

## 5. Tell them what happened

Say, in plain language:

- Their knowledge lives in the folder `status` reported, shared by every project and assistant on the machine.
- **They must restart the assistant once** — including this session, if you are Claude Code or Codex. The tools appear only in a session started after setup. This is the one step they have to do.
- Afterwards they can just talk. Give them these to try:
  > Save this for later: `<a YouTube link>`
  > What could my saved material become?
  > Use my `<collection>` to review this.

Do not print command lines at them, walk them through Python, or explain MCP unless they ask.

## If you cannot run commands

A chat without command access (plain ChatGPT, for example) cannot install anything. Say so plainly, and offer the two real routes:

1. They run the setup on their own computer through a host that has command access (Claude Code, Codex, a terminal) — you can write out the three commands for them to paste.
2. Someone who already runs Lectic gives them a link from `lectic share`, which they add as a connector in their chat app's settings. No install needed on their side. See `docs/CLOUD.md`.

## If they want to use it from ChatGPT, Claude on the web, Gemini or their phone

Those cannot reach a local program, so they need a link. From a folder that is **not** a project with its own older `.expertise-compiler` storage (their home folder is a safe choice):

```
<python> -m lectic.cli share
```

**It runs until stopped.** Start it in the background, then read the link with `<python> -m lectic.cli status`, which prints it once it is live. Do not run it in the foreground and wait — it will not return.

Give the person the link and where to paste it: ChatGPT → Settings → Apps & Connectors → Create (Authentication: none); Claude → Settings → Connectors → Add custom connector; Gemini CLI → `gemini mcp add --transport http lectic <link>`. Their phone can post saves to the same link; see `docs/CLOUD.md`.

Tell them plainly: the link works while that command keeps running, a quick tunnel gets a new address each time, and **anyone with the link can read and change their knowledge**, so it is not for posting publicly. If they want it always on, point them at the container in `docs/CLOUD.md`.

If it reports that `cloudflared` is missing, install it with their approval (`winget install Cloudflare.cloudflared`, `brew install cloudflared`) and run it again.

## If they are moving to a new machine, or want a backup

```
<python> -m lectic.cli backup              # one archive file with everything
<python> -m lectic.cli restore <file>      # merge it in on the other machine
<python> -m lectic.cli push <link>         # send this knowledge to a Lectic running elsewhere
<python> -m lectic.cli pull <link>         # bring that one's knowledge here
```

Merging only ever adds. Report what the command says: collections added, ones already present, and any it kept apart because they exist on both sides and differ — do not describe that as a failure, and never suggest deleting one side to "fix" it. Repeating any of these is safe.

## If they asked you to install a knowledge pack

```
<python> -m lectic.cli install <file or https link>
```

Report exactly what it says: `verified`, or `partial` with the sources and reasons it names. Do not describe a partial install as complete. `--inspect` shows what a pack contains without installing it.

## Ground rules

Lectic stores knowledge in one home per user, never inside their project, and never inside the installed package. Do not create a `.expertise-compiler` folder in a project, hand-edit an assistant's MCP config, or install anything beyond `lectic` and optionally `yt-dlp` without asking. If you are already connected to Lectic's tools, use them rather than running scripts: `lectic_home`, `lectic_library`, `lectic_work`, `lectic_capture_save`, and the rest are documented in `docs/MCP.md`.

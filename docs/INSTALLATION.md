# Install Lectic as a skill

Lectic is the new product name; `expertise-compiler` remains the compatible installed skill identifier. Existing installations and `.expertise-compiler/` data folders do not need renaming. The repository root is the skill. Keep its name `expertise-compiler` and include supporting folders, not just SKILL.md. Give the installation message in the README to your assistant; no manual terminal setup is needed.

## Codex

Ask `$skill-installer` to install the root of `tyreamer/lectic` under the explicit name `expertise-compiler`. The repository-relative skill path is `.`. The installed helper resolves its supported personal skill directory; follow it rather than assuming one universal directory across Codex versions. For a local development copy, ask Codex to use this repository's clean-copy installer with its personal skill directory as the destination.

New installations are normally detected automatically; restart if absent. Describe your actual task, for example: “Use the transcripts in ./input to review my draft in ./plan.md for missing steps. Save this collection as Project Training for future work.” An explicit `$expertise-compiler` mention is an optional fallback. [Official Codex installation guidance](https://learn.chatgpt.com/docs/build-skills).

## Claude Code

Ask Claude Code to download/review the repository and install it at `~/.claude/skills/expertise-compiler`. This personal skill works across local projects. A project-scoped alternative is `.claude/skills/expertise-compiler`. On Windows, the assistant resolves `~` to your user home.

Describe what you're working on and what would make the result useful, alongside the source files. If automatic matching does not activate it, use `/expertise-compiler` followed by that request. Personal local skills are distinct from web/account skill installations. [Official Claude Code skill locations](https://code.claude.com/docs/en/skills).

## Installation contents

For a first real task and reuse checks, follow the [alpha testing guide](testing-guide.md).

The bundled `scripts/install_skill.py` copies reviewed local skill files: scripts, prompts, schemas, fixtures, and guidance. It excludes `.git`, user workspaces, and caches and refuses to overwrite a differing installation. It makes no network requests; downloading is the host assistant/installer's responsibility.

The installation may live outside your project, including paths with spaces. Runs live separately in the current project's `.expertise-compiler/`. Generated capabilities can be used immediately from their saved locations; global installation or publishing happens only when requested.

If setup is blocked, ask the assistant to diagnose unavailable skill discovery, missing file/command access, or the missing local runtime. It should explain the specific blocker and help resolve it without teaching you compiler commands. File-access policies may require permission. A web-only chat cannot replace local execution in this MVP.

The clean installer continues to refuse differing installations. Use the separate updater below when an existing copy needs updating. Exact clean-install invocation is in [DEVELOPING.md](DEVELOPING.md).

## Updates

Ask your assistant:

> Update Lectic and enable automatic updates on this PC.

Or: “Is my installed Lectic current?”, “Check for an update now”, “Pause Lectic updates”, or “Turn automatic updates back on.” No terminal work is required from the user; the assistant operates the helpers below. Only enable periodic updates when requested.

The updater follows **`tyreamer/lectic`, branch `main`**. This is the current development channel, not a separately certified stable release. It downloads a pinned commit over HTTPS, validates the payload, parses Python/JSON, stages replacement, and retains the old installation. These checks verify packaging, not effectiveness or freedom from all software bugs. No model calls, subscription, GitHub login, or always-running service is required.

The installed copy is separate from a checkout. Updates never pull into a developer's working repository, extract a collection, regenerate a Capability Map, or mutate an older built artifact. Existing data stays under each project's `.expertise-compiler/`. The updater refuses a destination containing Git state or project data. Its scope is the compiler skill's instructions and supporting files.

An existing copy without an update receipt needs one explicit enrollment. The `--adopt` operation retains **the entire existing installation**, including unrecognized files, in a backup before installing the published payload. It does not merge customizations. Thereafter, added, deleted, or modified installed files prevent replacement; `--adopt` cannot override this check. Python bytecode caches are ignored. Review local edits instead of removing the receipt to bypass protection.

The current state, exact commit, last check, last result, changed files and backup paths are available with “Show Lectic's update status.” State and backups live outside the skill discovery directory, normally `~/.codex/lectic-updates/expertise-compiler/` for an installation at `~/.codex/skills/expertise-compiler`. Other supported skill roots get an adjacent `lectic-updates/` directory. Receipts use version `1.0`, with a destination binding, upstream repository/ref, file SHA-256 hashes, commit, check interval and backup history. They are distribution metadata, separate from Expertise IR.

On **Windows**, the optional per-user scheduled task wakes hourly and at login, but contacts GitHub at most once every 24 hours. It runs without a console window, administrator privileges, stored password or AI session, and only while the user is logged in. Missed checks catch up when the machine/user is available. Offline checks, download failures, file locks and local edits preserve the installation and leave a `needs_attention` result for the assistant to explain. There are no push notifications. “Check now” bypasses the time gate; it does not bypass local-edit protection.

The independent runner can recover an interrupted folder replacement even when the installed directory is temporarily absent. Backups and adjacent `.receipt.json` files are retained until deliberately removed. To restore a backup, pause updates first, inspect the desired version and have the assistant restore it with its matching receipt; don't delete or reset receipts as a shortcut. A restored older version must remain paused until an update is wanted.

The downloaded payload is refreshed on disk. Use a new turn/task for new instructions; if the host still shows old metadata, restart it. Existing in-progress tasks may have cached instructions. Avoid updating manually midway through an active build.

### Assistant/contributor operations

Run the updater from a reviewed checkout for the first enrollment, using the actual installed location. The old installed copy might not yet contain it:

```text
python /path/to/lectic/scripts/update_skill.py update --dest /path/to/skills/expertise-compiler --adopt
python /path/to/skills/expertise-compiler/scripts/update_skill.py status --dest /path/to/skills/expertise-compiler
```

To enable the Windows schedule after enrollment:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\lectic\scripts\enable_updates_windows.ps1" -Destination "C:\path\to\skills\expertise-compiler" -Python "C:\path\to\python.exe"
```

The setup checks the managed installation, creates a task for the current user, then enables the update receipt. Inspect the returned task name, action and next run, and exercise the task once before reporting success. Re-running setup is idempotent for that installation; it refuses to overwrite an unrelated task. `-Disable` pauses checks and removes that exact task. The simpler `update_skill.py pause --dest ...` leaves the task registered but makes it a no-op.

Subsequent manual updates use `update_skill.py update --dest ...` without `--adopt`. `status` is read-only and reports the most recent successful comparison; it does not contact GitHub. The standalone runner lives at `<state directory>/runner.py` and is refreshed after successful updates. It accepts the same commands and remains usable during recovery.

On macOS/Linux, the Python updater can be run manually. Automatic scheduler setup for those platforms is not supplied yet; `enable` sets the receipt flag only and does not create an OS schedule.

### ChatGPT versus the local skill

These instructions update the **local filesystem skill** used by the assistant that can access that folder. They do not update an uploaded ChatGPT workspace skill, account knowledge files, installed plugins, or ChatGPT/Codex itself. Those are separate installation/distribution paths. Do not claim that a user's separate ChatGPT copy is current without inspecting that installation. [Official OpenAI distribution guidance](https://learn.chatgpt.com/docs/enterprise/skills#skill-distribution-and-administration).

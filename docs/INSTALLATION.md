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

Preserve prior installations during updates; the clean installer does not silently replace a different folder. Exact helper invocation is in [DEVELOPING.md](DEVELOPING.md).

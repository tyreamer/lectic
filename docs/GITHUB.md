# Your packs, in your GitHub

**Product direction:** try Lectic in your AI first. Connect GitHub when you want to keep your packs. The public entry point is this repository and its GitHub Pages guide. Each person's saved library belongs in their own private GitHub repository; local Lectic is a working copy.

There is no separate Lectic account in this route. GitHub Pages serves the guide, prompts and example downloads. It does not run the Python compiler. An assistant with Lectic tools builds validated packs; another chat can use a readable context file without those tools.

## First time

Give your AI two or three sources you care about and a real task:

> Help me turn these sources into reusable context. Suggest one useful way to apply it to my work, plus two alternatives. Make the first result with me. If you cannot access a source, tell me what to attach or paste.

No GitHub account is needed to try this. Without Lectic tools, the result is a draft in your chat, not a saved or verified Lectic pack. With Lectic available, your assistant can build a pack and try it locally before connecting GitHub. No examples are added automatically.

When it is worth keeping:

> Keep this as a Lectic pack in my private GitHub library. Help me connect GitHub and check that it actually saved.

An assistant with command access can handle repository setup and pack sync. You complete GitHub's sign-in yourself. If you have no account, it can take you to [GitHub signup](https://github.com/signup) at this point. Never paste passwords or tokens into chat.

Use the same pack for a second task. Send a selected readable export to someone else so they can find their own use. A private repository URL alone does not grant your AI or another person access.

## Implemented in this branch

- `lectic github connect OWNER/lectic-packs --create` creates a **private**, initialized repository in the signed-in user's account and syncs prepared packs. Omit `--create` for an existing dedicated private repository.
- `lectic sync` pulls remote changes and uploads local changes. The assistant can use `lectic_github` for the same operations and status.
- The local MCP server checks every five minutes while running, including an initial check on startup. Multiple assistants share a per-home sync lock and retry timestamp. There is no OS background service when all assistants are closed.
- Each prepared pack has an immutable `.lectic` revision and a readable `.md` companion containing its knowledge, quotations and source references. A single Git commit updates both files and the library index.
- Full source **text** is included for restoration. Pending captures, unfinished packs, original audio/video/image attachments, results, secrets and personal account configuration are not synced. This is pack sync, not a whole-machine backup.
- Offline work stays local until retry succeeds. Both-sided edits are reported for review; neither revision is silently selected or deleted. Remote deletions do not delete local work. Old Git revisions remain available.
- Sync stops if the repository becomes public, loses write access or a competing commit wins. There is no force push.
- `lectic github status` reports the last sync, pending packs and conflicts. `lectic github disconnect` stops syncing and preserves both copies.

Authentication uses an existing GitHub CLI sign-in (`gh auth login`) or `GH_TOKEN`/`GITHUB_TOKEN` supplied outside chat. Credentials are never written to the library or packs. Existing-repository access needs Contents read/write. Use a dedicated private pack repository; sync rejects an unrelated populated project. This implementation supports github.com, up to 500 packs and 20 MB per packed revision.

## Verification and release limits

The automated tests exercise the actual compiler and pack format against a simulated GitHub API in isolated homes. A separate live GitHub probe on September 26, 2026 created a dedicated private repository, uploaded the authored Debugging Starter, restored it into a second isolated home, changed and synced actual knowledge in both directions, verified repeat sync creates no extra commit, preserved conflicting edits, and disconnected without losing local work. The test repository was archived afterward. No personal content or preview library was used. See [recorded live evidence](reviews/2026-09-26-github-live-check.json).

Local validation on September 26, 2026: the 295-test regression run passed; the final expanded sync suite passed all 17 tests. CLI and MCP transport checks passed, as did the TypeScript/Vite production build and seven-stage offline release gate. Desktop and 390 px browser checks covered the start page, GitHub disclosure and prompt copying, with no horizontal overflow. One Windows HTTP connection aborted in a targeted rerun; all four HTTP tests passed on retry. The live probe used two isolated homes on one Windows machine; separate physical devices, new-user sign-in, real interrupted transfers and sustained background sync remain unverified.

Conflicts currently preserve both revisions and report what happened, but have no guided resolution command. Deleting a pack on GitHub preserves its local copy and asks for attention. These are developer-preview behaviors, not completed nontechnical onboarding.

GitHub storage alone does not give every web/mobile chat the ability to run Lectic or write to a private repository. That depends on the chat's tools and permissions. A read-only GitHub integration is insufficient for saving. Use a readable attachment for reuse; do not promise universal build-and-save support until each app is verified.

The earlier hosted-account app remains an experimental implementation. It is not the default onboarding or a prerequisite for GitHub pack storage. No hosted Lectic deployment is needed for this route.

References: [GitHub Pages is static hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Git database references and non-forced updates](https://docs.github.com/en/rest/git/refs).

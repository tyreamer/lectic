# Save from your iPhone to WayKit

The daily flow is **Instagram → Share → Save to WayKit → Saved**. It also works
with links or selected text from Safari and other apps. Your computer can be off.

The free deployment uses a Cloudflare Worker and D1 database for immediate,
durable phone saves, with the existing Python WayKit service on Render's free
plan. No paid disk or paid service is needed. [render.yaml](../render.yaml) and
[the Worker configuration](../hosting/cloudflare/wrangler.jsonc) define the setup.
Your library is imported once, and assistants connect to the same private HTTPS
address. The Python filesystem is a replaceable cache: acknowledged changes are
committed to durable storage before the assistant receives a successful response.

Render's free service sleeps after inactivity and can take about a minute to
wake for an assistant task. Phone shares are saved immediately in D1 even while
it sleeps; they are imported into the library when Python next handles a task.
Free platform quotas apply. This deployment never upgrades a plan automatically.
The initial personal-library limits are 3000 files and 256 MB of uncompressed
knowledge. See [Cloudflare limits](https://developers.cloudflare.com/d1/platform/limits/)
and [Render free hosting](https://render.com/docs/free).

## One-time iPhone setup

The assistant supplies your private capture address after deployment. A connector
address ending in `/mcp` has a capture address at the same location ending in
`/capture`. Treat this address like a password: anyone holding it can access your
library. Keep it in your own Shortcut; do not publish or share the configured one.

In Apple's Shortcuts app, create **Save to WayKit** and enable **Show in Share
Sheet**, accepting URLs and Text. Stop when no input is supplied; do not read the
clipboard automatically. Add these actions:

1. **Get Text from Input**, using **Shortcut Input**. This retains any text that
   Instagram shares alongside the link.
2. **Get Contents of URL**, using your private capture address. Set Method to
   **POST**, Request Body to **JSON**, and add a Text field named **value** with
   the previous action's Text variable. Use the JSON field editor rather than
   manually pasting text inside JSON quotes.
3. **Get Dictionary Value**, selecting **confirmation** from the response, then
   **Show Notification** with that value. A successful reply has `saved: true`;
   a network or authentication error is not a save confirmation.

This is a tested HTTP contract and a Shortcut recipe, not a signed installable
Shortcut. A first save must still be checked on the actual iPhone.

Apple documents [Share Sheet setup](https://support.apple.com/guide/shortcuts/apd163eb9f95/ios)
and [web API requests](https://support.apple.com/guide/shortcuts/apd58d46713f/ios).

## What is saved

The shared link, any supplied text and your note are saved in the server's library.
An Instagram link alone does not include the post's video, audio or caption.
WayKit currently saves Instagram links as references; it does not retrieve the
post or invent its contents. Any text actually shared with the link is retained.

## ChatGPT and your other assistants

Connect ChatGPT on the web to the same hosted WayKit library, then ask it to save
or use that library in conversation. Current custom MCP apps are web-only; this
does not add a WayKit connector to the native ChatGPT iPhone app. The direct
Shortcut is the phone save route. See [OpenAI's current availability](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt).

Connect Codex and Claude Code to the hosted address too. They then read the same
central library as the phone. Your local home remains a preserved backup; import
the hosted archive when you want an updated local copy. Server signing identity
and resume pointers survive Python restarts, but machine credentials are excluded
from portable knowledge archives.

## First real-device check

Share one Instagram link through the Shortcut and confirm the Saved notification.
Ask a connected assistant to show the most recent save and check the exact link.
Repeat with the computer shut down. Do not label the iPhone flow verified until
these actual-device checks pass.

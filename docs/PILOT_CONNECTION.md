# Connect Lectic to your AI

Lectic must be available as a tool in your conversation so your assistant can save sources, build packs and return to them later. Each participant needs their own library.

## Current status

The existing Lectic edition supports local assistant connections and a private remote connection to one Lectic home. The new account-based web pilot does **not** yet provide a personal hosted assistant connection or self-service connection signup. Its pack-sharing links do not connect an assistant to your library.

The [first-time guide](PILOT_FIRST_TIME.md) is for a participant with a tested personal connection. If that connection is missing, setup is incomplete. Having someone else prepare the participant's pack does not satisfy this pilot.

## Connect your assistant

### ChatGPT, Claude or Gemini

You need a live, private Lectic connection URL for **your own library** before adding it to your assistant. Your pilot invitation must include that URL and identify which assistant it has been tested with. Keep it private: the existing edition's connection link grants access to read and change the library.

Use the route for your app:

| Assistant | One-time connection |
| --- | --- |
| ChatGPT | Enable Developer mode in **Settings → Security and login**, then add the Lectic server URL through **Plugins → +**. Start a conversation and enable that connection. Availability depends on your account and workspace policy. [OpenAI instructions](https://developers.openai.com/plugins/deploy/connect-chatgpt). |
| Claude | Open **Customize → Connectors → + → Add custom connector** and add the Lectic server URL. Enable the connector in your conversation. Team accounts may need an owner to add it first. [Claude instructions](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp). |
| Gemini | In the web app, open **Settings → Connected Apps → Custom apps**, add the Lectic server URL and follow the connection steps. Use `@` to select it in chat. Google's current requirements include a personal account, age 18+, US location, English and Keep Activity enabled. [Google instructions](https://support.google.com/gemini/answer/17209137). |

These are the vendors' documented connection routes, checked September 26, 2026. They establish platform support; they do **not** establish that the Lectic pilot has passed a full workflow in each app. A missing menu, failed authentication or missing save/build tools is a setup blocker to report.

### Codex or Claude Code

These assistants can install the local edition for you. Ask:

> Set up Lectic for me: https://github.com/tyreamer/lectic

Let the assistant complete its checks, then restart it once. Continue with the connection check in the [first-time guide](PILOT_FIRST_TIME.md#1-connect-lectic-to-your-ai).

### Another assistant

It needs a connection that can call Lectic's tools to read **and write** your library. Gemini CLI also supports this protocol; see its [MCP connection guide](https://geminicli.com/docs/tools/mcp-server/). A chat that only reads an attached pack can use the knowledge, but has not connected to Lectic to build or save packs.

## Before sending pilot invitations

This section is for the pilot operator. Complete the connection work before recruiting participants for the self-service flow:

1. Provide a separate, empty home and private connection for each participant, or finish the authenticated connection to their hosted pilot account. Never distribute one shared connection to the operator's library. The existing single-home setup is documented in [remote hosting](CLOUD.md).
2. Verify the actual assistant and account can connect, save the participant's sources, distill a pack, show evidence and create a useful result. A tool handshake alone is insufficient. File attachments also need to reach Lectic; don't assume an assistant's attachment is accessible on the server.
3. In a new conversation, retrieve the saved pack and produce a different output without repeating ingestion. Confirm a second participant cannot reach the first participant's library.
4. Test exporting and importing the pack, an expired or revoked connection, and recovery from an unreadable source. Record unsupported apps and inputs. A published server-side file path is not a participant download.

A personal connection grants access to the library; an exported pack shares only that pack. A local tunnel works only while its server is running. Connecting all users through an always-on hosted service remains deployment work; no cloud resources have been provisioned for this pilot.

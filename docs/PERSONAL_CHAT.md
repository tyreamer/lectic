# Your personal Lectic, in your AI chat

**Direction update:** this hosted-account implementation is experimental. The default route is now [try in your AI, then keep packs in your private GitHub repository](GITHUB.md). A hosted Lectic account is not required for that route.

**Implementation status:** available in the local pilot code. Hosted activation and live ChatGPT, Claude and Gemini checks are still pending. This guide does not announce a public service.

## For a pilot participant, after activation

1. Open **Connect AI** in the invited Lectic pilot and copy its connection address.
2. Add it as a custom connection in your AI app. Choose **OAuth** if asked. Sign in to Lectic with your invited email and select **Connect my Lectic**.
3. Return to your chat, enable/select Lectic if your app requires it, and give it your own links or notes:

   > Save these sources in Lectic and build a reusable pack. Based on what you know about me, suggest one useful way to put it to work and two alternatives.

4. Choose an idea, or ask for something else. Later, try:

   > Use that same pack to help me with [another task].

Your library starts empty. You do not send your sources to the person who invited you, install Python, or supply a model key. A prompt alone cannot establish the connection.

For a quick save, say **“Just save this for later.”** Lectic stores it without starting retrieval or paid processing. Your AI can read an existing pack and create something in the conversation; it can also request a saved creation inside Lectic. The latter uses the pilot's processing allowance.

If your chat does not expose an attached file to its tools, Lectic cannot silently transfer it. Supply the readable text or use **Library → Choose files** in your own account. The AI can use it after upload. Blocked links stay saved and ask for the missing content; a thumbnail or caption is not treated as the complete source.

To share, ask your AI to share a particular pack. An unlisted link contains one fixed pack version; invited recipients can copy it and use it differently. **Connect AI → Disconnect** revokes an AI app's future access. Revoking a pack link is separate. Neither operation recalls content already received.

Connection settings and availability vary by provider: [ChatGPT custom apps](https://developers.openai.com/plugins/deploy/connect-chatgpt), [Claude custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [Gemini custom apps](https://support.google.com/gemini/answer/17209137). Other apps need remote MCP with OAuth. A readable context export remains usable as an attachment where custom connections are unavailable.

## How the implementation works

- The public address is `<LECTIC_ORIGIN>/mcp`. It contains no credential and selects no tenant. Each request derives its account from a validated OAuth token.
- Supabase supplies authorization-code/PKCE, client registration, consent records, refresh tokens and grant revocation. Lectic supplies the consent UI at `/connect/approve` and preserves its pending request through Google/Apple sign-in.
- Protected-resource discovery is served at `/.well-known/oauth-protected-resource/mcp` and the root well-known path. Missing authentication receives a `401` with the metadata URL. The authorization-server issuer is the dedicated project's `/auth/v1` URL.
- A dedicated-project token hook assigns OAuth tokens the exact MCP resource audience. The API validates signature/current user through Supabase, then issuer, audience, subject, expiry, OAuth client ID, active session and invitation. Browser API requests reject OAuth-client tokens; the MCP endpoint rejects ordinary browser tokens. No development identity bypass applies to MCP.
- The migration also prevents OAuth clients from directly accessing Lectic database tables or private originals through the Supabase data APIs. The consent describes access to the person's library, capture/creation and requested sharing. Supabase's `email` scope describes identity information; it is **not** a read/write permission boundary. This pilot does not claim granular OAuth scopes or read-only connections.
- The stateless Streamable HTTP endpoint supports JSON responses for MCP versions `2025-11-25`, `2025-06-18` and `2025-03-26`. It deliberately offers no SSE subscription or connection session credential.
- An explicit tool registry calls the same owned API operations as the web app. No tool accepts a filesystem path, tenant, arbitrary route or executable code. Mutations reuse durable operation IDs and retry keys; paid work remains in per-account compiler subprocesses and the existing spending ledger.
- Shared proactive guidance tells the agent to inspect evidence, use relevant context actually available in the conversation, recommend a concrete personal use, respect quick saves/dismissals, and ask before sharing when sharing has not been requested.

| Tools | Purpose |
|---|---|
| `lectic_library`, `lectic_read`, `lectic_evidence` | Discover owned material, read paginated context/results, resolve exact source passages |
| `lectic_capture_save`, `lectic_process_source`, `lectic_build_pack` | Save immediately, prepare when requested, distill Ready sources |
| `lectic_create`, `lectic_operation` | Optional saved generation; progress, cancellation and retry |
| `lectic_share_pack`, `lectic_shares`, `lectic_revoke_share`, `lectic_copy_shared_pack` | Explicit fixed-pack sharing, revocation and independent recipient copies |

## Operator activation — dedicated accounts only

No resources were provisioned for this implementation. Keep `LECTIC_CHAT_ENABLED` unset until these steps and the live checks below are complete. The local preview intentionally offers no public connection address.

1. Follow [PILOT.md](PILOT.md) for the dedicated database, worker, secrets, HTTPS origin and invited users. Apply both migrations in `supabase/migrations`, including `20260926202602_personal_chat_connection.sql`.
2. In that server environment run `python -m lectic.cloud.admin configure-chat`. It records the canonical HTTPS resource in the private configuration table. Changing domains requires rerunning this command and reconnecting clients.
3. In Supabase Auth, enable the OAuth 2.1 server and dynamic client registration. Set the Site URL to `LECTIC_ORIGIN` and the authorization path to `/connect/approve`. Register only the intended browser sign-in redirects, including `/connect/approve?authorization_id=*` and `/?view=connections`; avoid a wildcard over unrelated domains. Keep the chosen Google/Apple providers and disable unwanted authentication methods.
4. Enable `public.lectic_access_token_hook` as the **Custom Access Token** hook. This is required, not optional: tokens with the default `authenticated` audience are rejected by `/mcp`. Use a dedicated project; the hook applies the Lectic audience to all its OAuth clients. If a hook already exists, compose its behavior instead of overwriting unrelated logic.
5. Set `LECTIC_CHAT_ENABLED=1` in the isolated hosted verification environment and restart the API. Check discovery and the real token audience before distributing the address. The endpoint is still invitation-gated.
6. Verify each provider route below before calling that provider supported in the live pilot. A provider that cannot discover/register with the Supabase authorization server needs manual client registration or further compatibility work; do not tell a participant the connection succeeded prematurely.

Supabase documents [MCP authentication](https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication), [authorization flows](https://supabase.com/docs/guides/auth/oauth-server/oauth-flows), and [OAuth token security and audience hooks](https://supabase.com/docs/guides/auth/oauth-server/token-security). The resource server follows the [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization).

## Verification and remaining launch gates

Local contract checks exercise real API/tool handlers and the compiler against isolated temporary homes. External identity/model responses are deterministic fixtures. Tests cover empty libraries; signature-verifier rejection; wrong issuer/audience/subject; expired tokens; revoked sessions/invitations; cross-account reads and mutations; quick saves and retries; two-source pack creation; two different saved results without repeating extraction; exact passage resolution; paginated context; accurate blocked-link states; recipient copies and share revocation.

Browser checks with a simulated authorization server cover approval, denial, disconnection, a pending request surviving sign-in, and 390 px layouts. They do not certify Google's login, Supabase's code exchange/refresh, or a deployed chat connection.

Before invitations, record:

- Real Google/Apple sign-in, client registration, PKCE exchange, resource/audience binding, refresh and expired-login recovery on the dedicated Supabase project. Inspect provider auth endpoints as well as Lectic endpoints; OAuth grants must not bypass intended consent, account-management or revocation boundaries.
- Two actual accounts in each enabled AI app, including attempts to use the other account's source, pack, job and result IDs. Verify database/storage RLS in PostgreSQL, not only SQLite.
- Disconnect a client while it has a valid access token. Both further calls and refresh must fail; browser access and other approved connections should remain available. Denial must leave no usable connection.
- Bring personal sources, build one pack, make a useful result in chat and reuse that pack for a different task. Check actual attachment visibility and state limitations plainly.
- Observe unaided use. The existing pilot's confusion is not resolved merely by a passing protocol test.

Live hosting, provider interoperability, SQL hook execution and real participant success remain unverified until those accounts are supplied and activated.

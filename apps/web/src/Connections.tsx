import { useEffect, useState } from "react";
import type { SupabaseClient, OAuthAuthorizationDetails, OAuthGrant } from "@supabase/supabase-js";
import { Glyph } from "./Icon";

type Props = {
  auth: SupabaseClient | null;
  signed: boolean;
  enabled: boolean;
  mcpUrl: string | null;
  login: (provider: "google" | "apple") => void;
  checkAccount: () => Promise<unknown>;
  loginError?: string;
};

function Login({login}: Pick<Props,"login">) {
  return <div className="actions"><button className="primary" onClick={()=>login("google")}>Continue with Google</button><button onClick={()=>login("apple")}>Continue with Apple</button></div>;
}

function follow(redirect: string) {
  // Only navigate to a URL supplied by the authorization server, never a query
  // parameter or client display URL. Also reject executable/data URL schemes.
  const url = new URL(redirect);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost","127.0.0.1","[::1]"].includes(url.hostname))) {
    throw new Error("This chat app returned an unsupported callback address.");
  }
  location.assign(url.href);
}

export function ConnectionConsent(props: Props & {authorizationId: string}) {
  const [details,setDetails] = useState<OAuthAuthorizationDetails|null>(null);
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  useEffect(()=>{
    if (!props.signed || !props.auth || !props.enabled) return;
    let active = true;
    setDetails(null);setError("");
    (async()=>{
      if(!/^[a-zA-Z0-9_-]{1,128}$/.test(props.authorizationId))throw new Error("This connection request is missing or expired. Start again in your AI chat.");
      await props.checkAccount();
      const {data,error} = await props.auth!.auth.oauth.getAuthorizationDetails(props.authorizationId);
      if(error)throw error;
      if(!active || !data)return;
      if("redirect_url" in data)follow(data.redirect_url);
      else setDetails(data);
    })().catch(e=>{if(active)setError(e.message)});
    return()=>{active=false;};
  },[props.signed,props.auth,props.enabled,props.authorizationId]);
  async function decide(approve:boolean) {
    if(!props.auth || !details)return;
    setBusy(true);setError("");
    try {
      await props.checkAccount();
      const method = approve ? "approveAuthorization" : "denyAuthorization";
      const {data,error} = await props.auth.auth.oauth[method](props.authorizationId,{skipBrowserRedirect:true});
      if(error)throw error;
      if(data)follow(data.redirect_url);
    } catch(e) {setError(e instanceof Error?e.message:"Connection could not finish. Try again.");setBusy(false);}
  }
  return <main className="connection-page"><a className="brand" href="/">lectic<Glyph name="brand"/></a>
    <section className="chat-prompt">
      <h1>Connect your Lectic</h1>
      {!props.enabled ? <p>Personal chat connections are not active on this server yet. Your local library remains private.</p> : !props.signed ? <>
        <p>Sign in to connect your own sources and packs to your AI chat.</p><Login login={props.login}/>
      </> : details ? <>
        <h2>{details.client.name} wants to use your Lectic</h2>
        <p>Connecting as <strong>{details.user.email}</strong>.</p>
        <ul><li>Read your saved sources, packs and creations.</li><li>Save your sources, build packs and make new creations within your processing limits.</li><li>Create or revoke pack-sharing links when you ask.</li></ul>
        <p>You can disconnect this app at any time. Your AI provider receives the content it reads; disconnecting cannot recall copies already received.</p>
        <details><summary>Connection details</summary><p>Client ID: {details.client.id}</p><p>Return address: {details.redirect_uri}</p><p>Identity information requested: {details.scope || "email"}</p><small>The app name is supplied by the app registering this request.</small></details>
        <div className="actions"><button className="primary" disabled={busy} onClick={()=>decide(true)}>{busy?"Connecting…":"Connect my Lectic"}</button><button disabled={busy} onClick={()=>decide(false)}>Not now</button></div>
      </> : !error && <p>Checking your connection request…</p>}
      {(error || props.loginError) && <div role="alert" className="error"><p>{error || props.loginError}</p><p>Return to your AI chat to start a new connection request.</p></div>}
    </section>
  </main>;
}

export default function Connections(props: Props) {
  const [grants,setGrants] = useState<OAuthGrant[]|null>(null);
  const [message,setMessage] = useState("");
  const [error,setError] = useState("");
  const [revoking,setRevoking] = useState("");
  useEffect(()=>{
    let active=true;
    setGrants(null);setError("");
    if(props.signed && props.auth && props.enabled) {
      props.checkAccount().then(()=>props.auth!.auth.oauth.listGrants()).then(({data,error})=>{
        if(error)throw error;
        if(active)setGrants(data||[]);
      }).catch(e=>{if(active)setError(e.message)});
    }
    return()=>{active=false;};
  },[props.signed,props.auth,props.enabled]);
  async function revoke(clientId:string) {
    if(!props.auth)return;
    setRevoking(clientId);setError("");
    try {
      const {error}=await props.auth.auth.oauth.revokeGrant({clientId});
      if(error)throw error;
      setGrants(old=>(old||[]).filter(g=>g.client.id!==clientId));setMessage("Disconnected. Your sources and packs are still here.");
    } catch(e){setError(e instanceof Error?e.message:"Could not disconnect. Try again.");}
    finally {setRevoking("");}
  }
  return <>
    <section className="intro"><p className="eyebrow">Connect once. Keep creating.</p><h1>Your Lectic,<br/>in your AI chat.</h1><p>Give your AI your sources. It can build a pack and help you put it to work.</p></section>
    {!props.enabled ? <section className="chat-prompt"><h2>Connection setup is being prepared</h2><p>This local preview cannot be reached from a hosted AI chat. The connection will appear here after the hosted pilot is activated.</p></section> : <section className="chat-prompt">
      <h2>Add Lectic in your AI's connection settings</h2>
      <p>Use this server address, choose OAuth if asked, then sign in and approve your connection.</p>
      <label htmlFor="mcp-url">Lectic server address</label><input id="mcp-url" readOnly value={props.mcpUrl||""}/>
      <button className="primary" onClick={async()=>{try{await navigator.clipboard.writeText(props.mcpUrl!);setMessage("Copied. Add it in your AI's connection settings.");}catch{setMessage("Select and copy the address above.");}}}>Copy connection address</button>
      <details className="connect-guide"><summary>Where do I add it?</summary>
        <p><strong>ChatGPT:</strong> add a custom app in Settings → Apps. Your account or workspace must allow developer-mode apps. <a href="https://developers.openai.com/plugins/deploy/connect-chatgpt" target="_blank" rel="noreferrer">ChatGPT steps</a></p>
        <p><strong>Claude:</strong> Settings → Connectors → Add custom connector. <a href="https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp" target="_blank" rel="noreferrer">Claude steps</a></p>
        <p><strong>Gemini:</strong> Settings → Connected Apps → Custom apps, where available. <a href="https://support.google.com/gemini/answer/17209137" target="_blank" rel="noreferrer">Availability and steps</a></p>
        <p>Other AI apps need remote MCP with OAuth support. If your app does not offer connections, readable pack exports still work as attachments.</p>
      </details>
      <h3>Then say this in your chat</h3><blockquote>Save these sources in Lectic and build a pack. Based on what you know about me, suggest a useful way to put it to work.</blockquote>
    </section>}
    {props.enabled && <section className="chat-prompt"><h2>Connected apps</h2>{!props.signed ? <><p>Sign in to manage your connections.</p><Login login={props.login}/></> : grants===null ? !error && <p>Checking connections…</p> : grants.length ? grants.map(g=><article className="connection-row" key={g.client.id}><div><h3>{g.client.name}</h3><small>Connected {new Date(g.granted_at).toLocaleDateString()}</small></div><button disabled={!!revoking} onClick={()=>revoke(g.client.id)}>{revoking===g.client.id?"Disconnecting…":"Disconnect"}</button></article>) : <p>No apps connected yet.</p>}</section>}
    {message && <p role="status">{message}</p>}{error && <p role="alert" className="error">{error}</p>}
  </>;
}

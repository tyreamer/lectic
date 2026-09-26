import { useState } from "react";
import { Glyph } from "./Icon";

const prompts = {
  sources: "Help me turn these sources into reusable context. Based on what you know about me, suggest one useful way to apply it, plus two alternatives. Help me choose and make something useful. Tell me if you cannot read any source.",
  pack: "Read this context pack. Based on what you know about me and what I'm working on, suggest three useful ways I could use it. If you need more context about me, ask one short question. Then help me put it to work.",
};
const setup = "Set up Lectic for me: https://github.com/tyreamer/lectic";
const keep = "Keep this as a Lectic pack in my private GitHub library. Help me connect GitHub and check that it actually saved.";

export default function StartHere({openLibrary,openConnections}:{openLibrary:()=>void;openConnections:()=>void}) {
  const [route,setRoute] = useState<"sources"|"pack">("sources");
  const [copied,setCopied] = useState("");
  async function copy(text:string) {
    try {await navigator.clipboard.writeText(text);setCopied("Copied. Paste it in your AI chat.");}
    catch {setCopied("Select and copy the prompt above.");}
  }
  return <>
    <section className="intro chat-intro">
      <p className="eyebrow">Your AI. Your sources. Reusable context.</p>
      <h1>Start in the chat<br/>you already use.</h1>
      <p>Try your sources on a real task. When the context is worth keeping, save a pack in your GitHub.</p>
      <p className="fine">No GitHub account needed to try. No separate Lectic account.</p>
    </section>
    <div className="chat-flow" aria-label="Sources become reusable context, then useful work">
      <span><Glyph name="note"/> Your sources</span><Glyph name="right"/>
      <span><Glyph name="sparkle"/> Something useful</span><Glyph name="right"/>
      <span><Glyph name="pack"/> Keep it in GitHub</span>
    </div>
    <section className="chat-prompt" aria-labelledby="chat-start-title">
      <h2 id="chat-start-title">Give your AI a starting point</h2>
      <div className="formats" role="group" aria-label="Starting point">
        <button className={route==="sources"?"selected":""} aria-pressed={route==="sources"} onClick={()=>{setRoute("sources");setCopied("");}}>Start with my sources</button>
        <button className={route==="pack"?"selected":""} aria-pressed={route==="pack"} onClick={()=>{setRoute("pack");setCopied("");}}>I have a pack</button>
      </div>
      <p className="prompt-context">{route==="sources" ? "Paste this in your AI chat with two or three sources you care about." : "Attach the readable context file in ChatGPT, Claude or Gemini, then ask this."}</p>
      <blockquote>{prompts[route]}</blockquote>
      <button className="primary" onClick={()=>copy(prompts[route])}>Copy prompt <Glyph name="share"/></button>
      <span className="copy-status" role="status">{copied}</span>
      {route==="pack" && <small>A readable .txt context export works without a Lectic connection. Use the library to download it.</small>}
      {route==="sources" && <small>Without Lectic tools, this first result is a draft in your chat. Your AI will help you set up Lectic when you want a saved pack.</small>}
    </section>
    <details className="connect-guide">
      <summary>Worth keeping? Save it in your GitHub</summary>
      <p>Your own private repository holds your packs. Local Lectic syncs its working copy while running. Create a GitHub account at this step if you need one.</p>
      <blockquote>{keep}</blockquote><button onClick={()=>copy(keep)}>Copy save request</button>
      <h3>Let your assistant handle setup</h3>
      <p>Codex and Claude Code can set up Lectic and GitHub access. You complete GitHub sign-in yourself. A restart may be needed once.</p>
      <blockquote>{setup}</blockquote><button onClick={()=>copy(setup)}>Copy setup request</button>
      <p>Other AI apps need tools that can run Lectic and write to your private repository. A prompt or repository link alone does not grant that access. You can always reuse a readable export as an attachment.</p>
      <small>Development preview: GitHub round-trip checks pass. Web/mobile saving and conflict resolution still need work.</small>
    </details>
    <details className="connect-guide"><summary>Development preview</summary><p>The earlier hosted app is available here for inspection. It is separate from your GitHub pack library.</p><button onClick={openLibrary}>Preview library</button><button onClick={openConnections}>Experimental chat connection</button></details>
  </>;
}

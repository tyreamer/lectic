import { useState } from "react";
import { Glyph } from "./Icon";

const prompts = {
  sources: "Save these sources in Lectic and distill them into a reusable context pack. Based on what you know about me and what I'm working on, suggest three useful ways to use it. Help me choose one and make something useful.",
  pack: "Read this context pack. Based on what you know about me and what I'm working on, suggest three useful ways I could use it. If you need more context about me, ask one short question. Then help me put it to work.",
};
const setup = "Set up Lectic for me: https://github.com/tyreamer/lectic";

export default function StartHere({openLibrary}:{openLibrary:()=>void}) {
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
      <p>Turn your sources into knowledge you can keep using. Bring the pack to another chat, another AI, or another person.</p>
    </section>
    <div className="chat-flow" aria-label="Sources become reusable context, then useful work">
      <span><Glyph name="note"/> Your sources</span><Glyph name="right"/>
      <span><Glyph name="pack"/> A context pack</span><Glyph name="right"/>
      <span><Glyph name="sparkle"/> Something useful</span>
    </div>
    <section className="chat-prompt" aria-labelledby="chat-start-title">
      <h2 id="chat-start-title">Give your AI a starting point</h2>
      <div className="formats" role="group" aria-label="Starting point">
        <button className={route==="sources"?"selected":""} aria-pressed={route==="sources"} onClick={()=>{setRoute("sources");setCopied("");}}>Start with my sources</button>
        <button className={route==="pack"?"selected":""} aria-pressed={route==="pack"} onClick={()=>{setRoute("pack");setCopied("");}}>I have a pack</button>
      </div>
      <p className="prompt-context">{route==="sources" ? "With Lectic connected, paste this alongside your links, notes or files." : "Attach the readable context file in ChatGPT, Claude or Gemini, then ask this."}</p>
      <blockquote>{prompts[route]}</blockquote>
      <button className="primary" onClick={()=>copy(prompts[route])}>Copy prompt <Glyph name="share"/></button>
      <span className="copy-status" role="status">{copied}</span>
      {route==="pack" && <small>A readable .txt context export works without a Lectic connection. Use the library to download it.</small>}
    </section>
    <details className="connect-guide">
      <summary>First time? Connect Lectic to your AI</summary>
      <p>Saving and building packs from chat requires a Lectic connection. A prompt alone does not connect your account.</p>
      <h3>Using ChatGPT or Claude on the web?</h3>
      <p>You need a private connection to a running Lectic. The local web preview does not provide an account connection yet.</p>
      <p><a href="https://github.com/tyreamer/lectic/blob/main/docs/CLOUD.md" target="_blank" rel="noreferrer">Connection guide <Glyph name="share"/></a></p>
      <h3>Using Codex or Claude Code?</h3>
      <p>These assistants can set up Lectic on your computer. Paste this, then restart the assistant when setup finishes.</p>
      <blockquote>{setup}</blockquote><button onClick={()=>copy(setup)}>Copy setup request</button>
      <h3>Already have a pack, or use Gemini?</h3>
      <p>Attach a readable context file to your chat. Choose “I have a pack” above for a starting question.</p>
    </details>
    <div className="library-entry"><div><h2>Your library is here when you need it.</h2><p>Add sources, inspect a pack, or download and share it.</p></div><button onClick={openLibrary}>Open my library <Glyph name="right"/></button></div>
  </>;
}

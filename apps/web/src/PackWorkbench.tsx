import { useEffect, useRef, useState } from "react";
import { Glyph } from "./Icon";

export type Idea = { title: string; description: string; format: string; brief: string; unit_ids: string[] };
type Props = {
  pack: {id?: string; slug?: string; starter?: string; title: string};
  api: (path: string) => Promise<any>;
  post: (path: string, body?: unknown, retryKey?: string) => Promise<any>;
  busy: boolean; signed: boolean; format: string; brief: string;
  select: (format: string, brief: string) => void;
  changeBrief: (brief: string) => void;
  create: () => void; back: () => void; share: () => void;
  inspect: () => void; download: () => void; exportContext: () => void; signIn: React.ReactNode;
};

const formats = ["Agent skill", "Prompt", "MCP server"];
const aiPrompt = "Based on what you know about me and what I am working on, suggest three useful ways I could use this context pack. Explain each in plain language. If you need to know more about me, ask one short question. Then help me choose a starting point.";
export default function PackWorkbench(p: Props) {
  const [info,setInfo] = useState<any>(null);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState("");
  const [editing,setEditing] = useState(false);
  const [situation,setSituation] = useState("");
  const [requestedContext,setRequestedContext] = useState<string>();
  const [copyStatus,setCopyStatus] = useState("");
  const briefInput = useRef<HTMLTextAreaElement>(null);
  useEffect(()=>{
    setInfo(null);setError("");setEditing(false);
    if(!p.pack.id || !p.signed)return;
    let stopped=false, timer:ReturnType<typeof setTimeout>;
    setLoading(true);
    const watch = async(job?:string)=>{
      try {
        const pack=await p.api("/packs/"+p.pack.id+(requestedContext === undefined ? "" : "?context="+encodeURIComponent(requestedContext)));
        if(stopped)return;
        setInfo(pack);
        if(pack.suggestions){setSituation(pack.suggestions.context || "");setLoading(false);return;}
        if(!job) {
          const operation=await p.post("/packs/"+p.pack.id+"/suggestions",{context:requestedContext || ""});
          job=operation.operation_id;
        }
        if(stopped)return;
        const operation=await p.api("/jobs/"+job);
        if(["failed","cancelled"].includes(operation.status))throw new Error("Suggestions aren't ready. You can still choose your own use below.");
        timer=setTimeout(()=>watch(job),2000);
      }catch(e){if(!stopped){setLoading(false);setError(e instanceof Error?e.message:"Suggestions unavailable.");}}
    };
    watch();
    return()=>{stopped=true;clearTimeout(timer);};
  },[p.pack.id,p.signed,requestedContext]);
  function select(format:string, brief:string){p.select(format,brief);setEditing(true);setTimeout(()=>briefInput.current?.focus(),0);}
  const template=(format:string)=>({
    "Agent skill":`Create a reusable agent skill that applies the methods and boundaries in ${p.pack.title}. Ask for the user's task, follow the distilled context, and cite evidence.`,
    "Prompt":`Create a reusable prompt that applies ${p.pack.title} to a future task. Include clear input placeholders, source rules and an output structure.`,
    "MCP server":`Make the context in ${p.pack.title} available to an AI assistant through a read-only MCP server. Include useful example queries and explain its boundaries.`,
  } as Record<string,string>)[format] || "";
  return <>
    <button className="text-button back-link" onClick={p.back}><Glyph name="left"/> Your sources & packs</button>
    <section className="context-heading">
      <span className="context-glyph" aria-hidden="true"><Glyph name="pack"/></span>
      <div>
        <p className="eyebrow">{p.pack.slug || p.pack.starter || info?.starter ? "Example context pack · Lectic-authored" : "Your context pack"}</p>
        <h1>{p.pack.title}</h1>
        <p>Your sources, distilled into knowledge you can use again.</p>
        {info && <small>{info.source_count} sources · {info.preview.units.length} distilled insights</small>}
      </div>
    </section>
    {p.pack.id && <div className="pack-actions"><button onClick={p.share}>Share pack <Glyph name="share"/></button><button onClick={p.inspect}>What's inside</button></div>}
    {!p.signed ? p.signIn : !p.pack.id ? <p role="status">Opening this example…</p> : <>
      <div className="section-heading"><div><h2>Where could this take you?</h2><p>A few starting points from your pack. You can always try something else.</p></div></div>
      <form className="personalize" onSubmit={e=>{e.preventDefault();setRequestedContext(situation.trim());}}>
        <label htmlFor="situation">What are you working on? <span>(optional)</span></label>
        <div><input id="situation" value={situation} onChange={e=>setSituation(e.target.value)} maxLength={1000} placeholder="A project, a decision, something you want to learn…"/><button disabled={loading || p.busy || situation.trim() === info?.suggestions?.context}>Suggest ideas for me</button></div>
      </form>
      {loading && <div className="suggestions-loading" role="status"><span className="spinner"/> Reading your context to find useful starting points…</div>}
      {error && <p role="status" className="muted">{error}</p>}
      <div className="idea-grid">
        {(info?.suggestions?.ideas || []).map((idea:Idea,i:number)=><button className="idea-card" key={i} disabled={p.busy} onClick={()=>select(idea.format,idea.brief)}>
          <h3>{idea.title}</h3><p>{idea.description}</p><span>Try this <Glyph name="share"/></span>
        </button>)}
        <button className="idea-card custom-idea" disabled={p.busy} onClick={()=>select("Your Idea","")}><h3>Something else in mind?</h3><p>Tell Lectic what you want to make, explore, or work through.</p><span>Start with your idea <Glyph name="share"/></span></button>
      </div>
      <details className="use-with-ai"><summary>Use this with ChatGPT or Claude <Glyph name="share"/></summary>
        <p>Take the context to the assistant that already knows you.</p>
        <ol><li><button onClick={p.exportContext}>Download context file <Glyph name="download"/></button></li><li>Attach the file in your chat.</li><li>Ask this, or ask anything you like:</li></ol>
        <blockquote>{aiPrompt}</blockquote>
        <button onClick={async()=>{try{await navigator.clipboard.writeText(aiPrompt);setCopyStatus("Copied");}catch{setCopyStatus("Select and copy the text above.");}}}>Copy question</button><span role="status" className="copy-status">{copyStatus}</span>
      </details>
      <details className="other-uses"><summary>Advanced options</summary><div className="formats">{formats.map(f=><button key={f} disabled={p.busy} onClick={()=>select(f,template(f))}>{f}</button>)}<button onClick={p.download}>Download .lectic pack <Glyph name="download"/></button></div></details>
      {editing && <section className="compose idea-compose">
        <div className="section-heading"><h2>{p.format === "Your Idea" ? "What would you like to make?" : "Make it yours"}</h2><button className="text-button" onClick={()=>setEditing(false)}>Close</button></div>
        <label htmlFor="brief">{p.format === "Review" ? "Paste what you want reviewed" : "Make it yours"}</label>
        <textarea ref={briefInput} id="brief" value={p.brief} onChange={e=>p.changeBrief(e.target.value)} maxLength={12000} placeholder="Tell Lectic what you want to create with this context…" rows={4}/>
        <button className="primary" disabled={p.busy || p.brief.trim().length<5} onClick={p.create}>{p.busy?"Creating…":p.format === "Your Idea"?"Make it happen":"Create "+p.format.toLowerCase()} {!p.busy && <Glyph name="sparkle"/>}</button>
        <small>{p.format === "MCP server" ? "Downloads a working server bundle. You choose where to connect it." : p.format === "Agent skill" ? "Downloads SKILL.md and its source context." : p.format === "Prompt" ? "A reusable prompt with the context included." : "Your pack supplies the context. You supply the direction."}</small>
      </section>}
    </>}
  </>;
}

export function ResultText({text}:{text:string}) {
  return <div className="prose">{text.split(/(```[\s\S]*?```)/g).map((part,i)=>{
    if(part.startsWith("```"))return <pre key={i}><code>{part.replace(/^```[^\n]*\n?/,"").replace(/```$/,"")}</code></pre>;
    const readable=part.replace(/\[See unit:[^\]]+\]\.?/gi,"").replace(/\s+(?=\d{1,2}\)\s)/g,"\n\n");
    return readable.split(/\n\s*\n/).filter(Boolean).map((paragraph,j)=><p key={i+"-"+j}>{paragraph}</p>);
  })}</div>;
}

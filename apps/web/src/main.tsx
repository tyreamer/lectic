import { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import "./style.css";

type Config = {
  dev: boolean;
  supabaseUrl: string;
  publishableKey: string;
  maxUpload: number;
  maxSources: number;
};
type Starter = {
  slug: string;
  title: string;
  icon: string;
  color: string;
  description: string;
  example: string;
  label: string;
};
type Card = {
  id: string;
  title: string;
  state?: string;
  kind?: string;
  reason?: string;
  format?: string;
  source_count?: number;
  needs_upload?: boolean;
};
type Operation = {
  id: string;
  kind: string;
  status: string;
  error?: string;
  result?: { pack_id?: string; result_id?: string; url?: string };
};
type Library = {
  sources: Card[];
  packs: Card[];
  results: Card[];
  operations: Operation[];
};
type Reference = {
  unit_id: string;
  title: string;
  quote: string;
  passage: string;
  caption_type: string;
  start: number | null;
  end: number | null;
  segment_id: string;
  url: string | null;
};
type Result = {
  id: string;
  title: string;
  markdown: string;
  references: Reference[];
  outcome: {
    summary: string;
    sections: {
      title: string;
      content: string;
      status: string;
      unit_ids: string[];
    }[];
    limitations: string[];
    unsupported: string[];
    additional_general_advice: string[];
  };
};
let auth: SupabaseClient | null = null;
let config: Config;
let sessionEpoch = 0;
async function api(path: string, options: RequestInit = {}) {
  const epoch = sessionEpoch;
  const session = auth ? (await auth.auth.getSession()).data.session : null;
  const headers: Record<string, string> = {
    ...(options.body && typeof options.body === "string"
      ? { "Content-Type": "application/json" }
      : {}),
    ...(options.headers as Record<string, string>),
  };
  if (session) headers.Authorization = "Bearer " + session.access_token;
  const response = await fetch("/api/v1" + path, { ...options, headers });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(
      typeof problem.detail === "string"
        ? problem.detail
        : response.status === 401
          ? "Please sign in again. Your work is safe."
          : "This could not be completed. Try again.",
    );
  }
  const value = response.status === 204 ? null : await response.json();
  if(epoch !== sessionEpoch)throw new Error("Signed out. Your work is saved.");
  return value;
}
const post = (
  path: string,
  body: unknown = {},
  retryKey: string = crypto.randomUUID(),
) =>
  api(path, {
    method: "POST",
    headers: { "Idempotency-Key": retryKey },
    body: JSON.stringify(body),
  });
const icons: Record<string, string> = {
  chat: "◌",
  code: "⌘",
  seed: "↗",
  note: "≡",
  url: "↗",
  upload: "▧",
  pack: "▱",
};
const provenance: Record<string, string> = {
  explicit: "Source statement", inferred: "Interpretation",
  synthesized: "Adapted from your pack", original: "Original advice",
  user_context: "Your context",
};
function Icon({ name }: { name: string }) {
  return (
    <span className={"icon " + name} aria-hidden="true">
      {icons[name] || "▱"}
    </span>
  );
}
function App() {
  const [ready, setReady] = useState(false),
    [signed, setSigned] = useState(false),
    [starters, setStarters] = useState<Starter[]>([]),
    [library, setLibrary] = useState<Library>({
      sources: [],
      packs: [],
      results: [],
      operations: [],
    });
  const [tab, setTab] = useState("Make"),
    [chosen, setChosen] = useState<{
      id?: string;
      slug?: string;
      title: string;
      example?: string;
    } | null>(() =>
      JSON.parse(sessionStorage.getItem("lectic-selection") || "null"),
    );
  const [format, setFormat] = useState(()=>sessionStorage.getItem("lectic-format") || "Plan"),
    [brief, setBrief] = useState(()=>sessionStorage.getItem("lectic-brief") || ""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [current, setCurrent] = useState<string | null>(()=>sessionStorage.getItem("lectic-operation")),
    [result, setResult] = useState<Result | null>(null);
  const autoCreate = useRef(sessionStorage.getItem("lectic-auto-create") === "1");
  const activeOperation = useRef(current);
  activeOperation.current = current;
  const [selected, setSelected] = useState<string[]>([]),
    [packName, setPackName] = useState(""),
    [captureText, setCaptureText] = useState(""),
    [share, setShare] = useState(""),
    [notice, setNotice] = useState("");
  const [source, setSource] = useState<any>(null),
    [preview, setPreview] = useState<any>(null),
    [myShares, setMyShares] = useState<
      { id: string; title: string; revoked: boolean }[]
    >([]);
  const file = useRef<HTMLInputElement>(null),
    fallback = useRef<string | null>(null),
    resumeUpload = useRef<string | null>(null),
    done = useRef(new Set<string>());
  const token = location.pathname.startsWith("/s/")
    ? location.pathname.split("/")[2]
    : null;
  useEffect(()=>{
    if(current)sessionStorage.setItem("lectic-operation",current);
    else sessionStorage.removeItem("lectic-operation");
    setBusy(!!current);
  },[current]);
  useEffect(()=>{
    sessionStorage.setItem("lectic-brief",brief);
    sessionStorage.setItem("lectic-format",format);
  },[brief,format]);
  useEffect(() => {
    if (result)
      document
        .getElementById("saved-result")
        ?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [result]);
  const report = (e: unknown) => {
    setError(e instanceof Error ? e.message : "Something went wrong.");
    setBusy(false);
  };
  const refresh = async () => {
    const next: Library = await api("/library");
    const active = activeOperation.current;
    if(active && !next.operations.some(o=>o.id===active)) {
      next.operations.push(await api("/jobs/"+active));
    }
    setLibrary(next);
  };
  useEffect(() => {
    (async () => {
      config = await api("/config");
      setStarters(await api("/starters"));
      if (config.dev) setSigned(true);
      else if (config.supabaseUrl && config.publishableKey) {
        auth = createClient(config.supabaseUrl, config.publishableKey, {
          auth: {
            flowType: "pkce",
            detectSessionInUrl: true,
            persistSession: true,
            autoRefreshToken: true,
          },
        });
        const { data } = await auth.auth.getSession();
        setSigned(!!data.session);
        auth.auth.onAuthStateChange((event, s) => {
          setSigned(!!s);
          if(event === "SIGNED_OUT") {
            sessionEpoch += 1;
            setLibrary({sources:[],packs:[],results:[],operations:[]});
            setChosen(null); setResult(null); setSource(null); setCurrent(null);
            setBrief(""); setShare(""); setMyShares([]); setSelected([]);
            setCaptureText(""); setPackName(""); setNotice(""); setError("");
            setTab("Make"); autoCreate.current = false; done.current.clear();
            sessionStorage.removeItem("lectic-auto-create");
          }
        });
      }
      if (token) setPreview(await api("/shared/" + token));
      setReady(true);
    })().catch(report);
  }, []);
  useEffect(() => {
    if (chosen)
      sessionStorage.setItem("lectic-selection", JSON.stringify(chosen));
    else sessionStorage.removeItem("lectic-selection");
  }, [chosen]);
  useEffect(() => {
    if (!ready || !signed) return;
    refresh().catch(report);
    post("/events", {
      name: localStorage.getItem("lectic-visited")
        ? "return_visit"
        : "first_visit",
    }).catch(() => {});
    localStorage.setItem("lectic-visited", "1");
    const timer = setInterval(() => refresh().catch(() => {}), 2500);
    return () => clearInterval(timer);
  }, [ready, signed]);
  useEffect(() => {
    const operation = library.operations.find((o) => o.id === current);
    if (!operation || done.current.has(operation.id)) return;
    if (operation.status === "complete") {
      if(operation.kind === "copy_share")setPreview(null);
      done.current.add(operation.id);
      setBusy(false);
      setCurrent(null);
      if (operation.result?.result_id)
        api("/results/" + operation.result.result_id)
          .then(setResult)
          .catch(report);
      if (operation.result?.pack_id) {
        const pack = library.packs.find(
          (p) => p.id === operation.result?.pack_id,
        );
        setChosen({
          id: operation.result.pack_id,
          title: pack?.title || chosen?.title || "Your pack",
        });
        setTab("Make");
        setNotice("Pack ready. What will you make?");
        if (autoCreate.current) {
          autoCreate.current = false;
          sessionStorage.removeItem("lectic-auto-create");
          setBusy(true);
          post("/creations", {
            pack_id: operation.result.pack_id,
            format,
            brief,
          })
            .then((op) => setCurrent(op.operation_id))
            .catch(report);
        }
      }
      if (operation.result?.url) setShare(operation.result.url);
    } else if (["failed", "cancelled"].includes(operation.status)) {
      done.current.add(operation.id);
      setBusy(false);
      setCurrent(null);
      if (operation.error) setError(operation.error);
    }
  }, [library, current]);
  async function login(provider: "google" | "apple") {
    setError("");
    if (!auth) return;
    const { error } = await auth.auth.signInWithOAuth({
      provider,
      options: { redirectTo: location.origin + (token ? "/s/" + token : "/") },
    });
    if (error) report(error);
  }
  async function choose(starter: Starter) {
    setChosen({
      slug: starter.slug,
      title: starter.title,
      example: starter.example,
    });
    setBrief(starter.example);
    setResult(null);
    setTab("Make");
  }
  async function make() {
    setError("");
    setBusy(true);
    try {
      if (!chosen) return;
      let id = chosen.id;
      if (!id) {
        autoCreate.current = true;
        sessionStorage.setItem("lectic-auto-create","1");
        const installed = await post(
          "/starters/" + chosen.slug + "/install",
          {},
          "starter-" + chosen.slug,
        );
        done.current.delete(installed.operation_id);
        setCurrent(installed.operation_id);
        setNotice("Adding your pack…");
        return;
      }
      const op = await post("/creations", { pack_id: id, format, brief });
      setCurrent(op.operation_id);
      setResult(null);
    } catch (e) {
      report(e);
    }
  }
  async function saveText() {
    setError("");
    setBusy(true);
    try {
      const isUrl = /^https?:\/\/\S+$/.test(captureText.trim());
      await post("/captures", {
        kind: isUrl ? "url" : "note",
        title: isUrl
          ? new URL(captureText.trim()).hostname
          : captureText.slice(0, 70),
        text: isUrl ? "" : captureText,
        url: isUrl ? captureText.trim() : "",
      });
      setCaptureText("");
      setNotice("Saved to Inbox");
      await refresh();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }
  async function upload(files: FileList | null) {
    if (!files) return;
    setError("");
    setBusy(true);
    try {
      for (const f of Array.from(files)) {
        if (f.size > config.maxUpload)
          throw new Error(f.name + " is over the 100 MB upload limit.");
        const key = crypto.randomUUID();
        let saved;
        if(resumeUpload.current) {
          const original = await api("/captures/"+resumeUpload.current);
          if(f.name !== original.data.filename || f.size !== original.data.size)
            throw new Error("Choose the same file to resume this upload.");
          saved = {capture_id:resumeUpload.current};
        } else saved = await post(
          "/captures",
          {
            kind: "upload",
            title: f.name,
            filename: f.name,
            size: f.size,
            parent_id: fallback.current,
          },
          key,
        );
        await api("/captures/" + saved.capture_id + "/content", {
          method: "PUT",
          headers: { "Content-Type": "application/octet-stream" },
          body: f,
        });
        resumeUpload.current = null;
        if (f.name.endsWith(".lectic")) {
          const op = await post("/packs/import/" + saved.capture_id);
          setCurrent(op.operation_id);
        }
      }
      fallback.current = null;
      setNotice("Saved. You can keep using Lectic while these process.");
      await refresh();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";
    }
  }
  async function assemble() {
    setError("");
    setBusy(true);
    try {
      const op = await post("/packs", {
        title: packName,
        source_ids: selected,
      });
      setCurrent(op.operation_id);
      setSelected([]);
      setPackName("");
    } catch (e) {
      report(e);
    }
  }
  async function sharePack(id: string) {
    setError("");
    try {
      const op = await post("/packs/" + id + "/shares");
      setCurrent(op.operation_id);
      setNotice("Preparing your fixed pack version…");
    } catch (e) {
      report(e);
    }
  }
  async function download(path: string, name: string) {
    try {
      const session = auth ? (await auth.auth.getSession()).data.session : null;
      const r = await fetch("/api/v1" + path, {
        headers: session
          ? { Authorization: "Bearer " + session.access_token }
          : {},
      });
      if (!r.ok) throw new Error("Download unavailable. Please sign in again.");
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      report(e);
    }
  }
  async function showShares() {
    try {
      setMyShares(await api("/shares"));
      setTab("Sharing");
    } catch (e) {
      report(e);
    }
  }
  if (!ready)
    return (
      <main className="loading">
        <div className="brand">
          lectic<span>✳</span>
        </div>
        <p>{error || "Opening your workspace…"}</p>
      </main>
    );
  return (
    <>
      <header>
        <a className="brand" href="/">
          lectic<span>✳</span>
        </a>
        <span className="pilot">
          {config.dev ? "Local development preview" : "Invited pilot"}
        </span>
        <nav>
          {signed ? (
            <>
              <button
                className={tab === "Make" ? "active" : ""}
                onClick={() => setTab("Make")}
              >
                Make
              </button>
              <button
                className={tab === "Library" ? "active" : ""}
                onClick={() => setTab("Library")}
              >
                Library
              </button>
              <button onClick={showShares}>Sharing</button>
              {!config.dev && <button
                aria-label="Sign out"
                onClick={async () => {
                  const response = await auth?.auth.signOut();
                  if(response?.error)report(response.error);
                }}
              >
                ↗
              </button>}
            </>
          ) : (
            <button onClick={() => login("google")}>Sign in</button>
          )}
        </nav>
      </header>
      <main>
        {error && (
          <div className="banner error" role="alert">
            {error}
            <button onClick={() => setError("")} aria-label="Dismiss">
              ×
            </button>
          </div>
        )}
        {notice && (
          <div className="banner" role="status">
            {notice}
            <button onClick={() => setNotice("")} aria-label="Dismiss">
              ×
            </button>
          </div>
        )}
        {token && preview && (
          <section className="shared">
            <p className="eyebrow">A pack, shared with you</p>
            <h1>{preview.title}</h1>
            <p>{preview.source_count} sources. Your next idea.</p>
            <div className="preview-grid">
              {preview.preview.units.slice(0, 6).map((u: any) => (
                <article key={u.id}>
                  <Icon name="pack" />
                  <h3>{u.title}</h3>
                  <p>{u.statement}</p>
                </article>
              ))}
            </div>
            {signed ? (
              <button
                className="primary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const op = await post("/shared/" + token + "/copy");
                    setCurrent(op.operation_id);
                    setBusy(true);
                  } catch (e) {
                    report(e);
                  }
                }}
              >
                Add my copy →
              </button>
            ) : (
              <SignIn login={login} />
            )}
            <small>
              A copy stays yours if the original link is later revoked.
            </small>
          </section>
        )}
        {tab === "Make" && !(token && preview) && (
          <>
            <section className="intro">
              <p className="eyebrow">Your sources. New possibilities.</p>
              <h1>
                {chosen
                  ? "What will you make?"
                  : "Start with something useful."}
              </h1>
              <p>
                {chosen
                  ? "One pack. Many possibilities."
                  : "Pick a pack. Make it yours."}
              </p>
            </section>
            <div
              className="flow"
              aria-label="Sources become a pack, then new work"
            >
              <span>
                ▧ <i>Sources</i>
              </span>
              <b>→</b>
              <span>
                ▱ <i>Pack</i>
              </span>
              <b>→</b>
              <span>
                ✦ <i>Your creation</i>
              </span>
              <b>↗</b>
              <span>
                ◎ <i>Share & reuse</i>
              </span>
            </div>
            {!chosen ? (
              <div className="starter-grid">
                {starters.map((s) => (
                  <button
                    className={"starter " + s.color}
                    key={s.slug}
                    onClick={() => choose(s)}
                  >
                    <Icon name={s.icon} />
                    <h2>{s.title}</h2>
                    <p>{s.description}</p>
                    <span className="card-action">
                      Make something <b>↗</b>
                    </span>
                    <small>{s.label}</small>
                  </button>
                ))}
              </div>
            ) : (
              <section className="workbench">
                <aside>
                  <div className="pack-spine">
                    <Icon name="pack" />
                    <p>Your pack</p>
                    <h2>{chosen.title}</h2>
                    <small>Reusable source-backed knowledge</small>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => {
                      setChosen(null);
                      sessionStorage.removeItem("lectic-selection");
                      setResult(null);
                    }}
                  >
                    Choose another pack
                  </button>
                  {chosen.id && (
                    <>
                      <button
                        className="text-button"
                        onClick={() => sharePack(chosen.id!)}
                      >
                        Share pack ↗
                      </button>
                      <button
                        className="text-button"
                        onClick={() =>
                          download(
                            "/packs/" + chosen.id + "/download",
                            "knowledge.lectic",
                          )
                        }
                      >
                        Download .lectic ↓
                      </button>
                      <button
                        className="text-button"
                        onClick={async () => {
                          try {
                            setSource(await api("/packs/" + chosen.id));
                          } catch (e) {
                            report(e);
                          }
                        }}
                      >
                        Inspect sources
                      </button>
                    </>
                  )}
                </aside>
                <div className="compose">
                  <div
                    className="formats"
                    role="group"
                    aria-label="What to make"
                  >
                    {[
                      "Plan",
                      "Checklist",
                      "Lesson",
                      "Review",
                      "Proposal",
                      "Your Idea",
                    ].map((f) => (
                      <button
                        key={f}
                        className={format === f ? "selected" : ""}
                        onClick={() => setFormat(f)}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                  <label htmlFor="brief">
                    {format === "Review"
                      ? "Paste the work you want reviewed"
                      : "Give it a little direction"}
                  </label>
                  <textarea
                    id="brief"
                    value={brief}
                    onChange={(e) => setBrief(e.target.value)}
                    maxLength={12000}
                    placeholder={
                      chosen.example ||
                      "Who is this for, and what do you want to achieve?"
                    }
                    rows={5}
                  />
                  {signed ? (
                    <button
                      className="primary"
                      disabled={busy || brief.trim().length < 5}
                      onClick={make}
                    >
                      {busy
                        ? "Creating…"
                        : "Create " + format.toLowerCase() + " ✦"}
                    </button>
                  ) : (
                    <SignIn login={login} />
                  )}
                  <small>AI-created work, with sources you can inspect.</small>
                </div>
              </section>
            )}
            {result && (
              <article className="result" id="saved-result">
                <div className="result-heading">
                  <div>
                    <p className="eyebrow">Made with your pack</p>
                    <h2>{result.title}</h2>
                  </div>
                  <div className="actions">
                    <button
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(result.markdown);
                          setNotice("Copied");
                          post("/events", {
                            name: "result_copied",
                            result_id: result.id,
                          }).catch(() => {});
                        } catch (e) {
                          report(e);
                        }
                      }}
                    >
                      Copy
                    </button>
                    <button
                      onClick={() =>
                        download(
                          "/results/" + result.id + "/download",
                          "lectic-result.md",
                        )
                      }
                    >
                      Markdown ↓
                    </button>
                  </div>
                </div>
                <p className="summary">{result.outcome.summary}</p>
                {result.outcome.sections.map((s, i) => (
                  <section key={i}>
                    <h3>{s.title}</h3>
                    <p className="provenance">{provenance[s.status] || "Check sources"}</p>
                    <div className="prose">{s.content}</div>
                    <details>
                      <summary>
                        {s.unit_ids.length
                          ? "Sources · " + s.unit_ids.length
                          : s.status === "original"
                            ? "Original advice"
                            : "Your context"}
                      </summary>
                      {result.references
                        .filter((r) => s.unit_ids.includes(r.unit_id))
                        .map((r, j) => (
                          <blockquote key={j}>
                            <p>{r.quote}</p>
                            <cite>
                              {r.title}
                              {r.start !== null ? " · " + r.start + "s" : ""}
                            </cite>
                            <details>
                              <summary>Original passage</summary>
                              <p>{r.passage}</p>
                              <small>
                                {r.caption_type === "automatic"
                                  ? "Automatic processing; check against the original."
                                  : r.caption_type === "synthetic"
                                    ? "Lectic-authored teaching material"
                                    : r.segment_id}
                              </small>
                            </details>
                          </blockquote>
                        ))}
                    </details>
                  </section>
                ))}
                {[
                  ...result.outcome.limitations,
                  ...result.outcome.unsupported,
                  ...result.outcome.additional_general_advice,
                ].length > 0 && (
                  <details>
                    <summary>Limits & additional advice</summary>
                    {[
                      ...result.outcome.limitations,
                      ...result.outcome.unsupported,
                      ...result.outcome.additional_general_advice,
                    ].map((l, i) => (
                      <p key={i}>{l}</p>
                    ))}
                  </details>
                )}
                <button
                  className="useful"
                  onClick={() => {
                    post("/events", {
                      name: "result_useful",
                      result_id: result.id,
                    })
                      .then(() => setNotice("Thanks — marked useful."))
                      .catch(report);
                  }}
                >
                  ✓ This is useful
                </button>
              </article>
            )}
          </>
        )}
        {tab === "Library" && (
          <>
            <section className="intro">
              <p className="eyebrow">Keep the good stuff</p>
              <h1>Your library.</h1>
            </section>
            <section
              className="capture-zone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                upload(e.dataTransfer.files);
              }}
            >
              <Icon name="upload" />
              <div>
                <h2>Drop your sources here</h2>
                <p>Links · notes · PDFs · images · audio · video</p>
                <div className="capture-input">
                  <textarea
                    aria-label="A link or note"
                    value={captureText}
                    onChange={(e) => setCaptureText(e.target.value)}
                    placeholder="Paste a link or a note"
                    rows={2}
                  />
                  <button
                    onClick={saveText}
                    disabled={busy || !captureText.trim()}
                  >
                    Save →
                  </button>
                </div>
                <button
                  className="text-button"
                  onClick={() => { resumeUpload.current = null; fallback.current = null; file.current?.click(); }}
                >
                  Choose files
                </button>
                <small>100 MB / file · 15 minutes / recording</small>
              </div>
            </section>
            <input
              ref={file}
              className="visually-hidden"
              type="file"
              multiple
              onChange={(e) => upload(e.target.files)}
            />
            <div className="section-heading">
              <h2>
                Inbox <span>{library.sources.length}</span>
              </h2>
              <p>Select ready sources to make a pack</p>
            </div>
            <div className="source-grid">
              {library.sources.map((s) => (
                <article
                  className={
                    "source-card " + (selected.includes(s.id) ? "checked" : "")
                  }
                  key={s.id}
                >
                  <div className="source-top">
                    <Icon name={s.kind || "note"} />
                    <input
                      type="checkbox"
                      aria-label={"Select " + s.title}
                      disabled={s.state !== "ready"}
                      checked={selected.includes(s.id)}
                      onChange={(e) =>
                        setSelected(
                          e.target.checked
                            ? [...selected, s.id]
                            : selected.filter((id) => id !== s.id),
                        )
                      }
                    />
                  </div>
                  <h3>{s.title}</h3>
                  <span className={"status " + s.state}>
                    {
                      (
                        {
                          saved: "Saved",
                          processing: "Processing",
                          ready: "Ready",
                          needs_content: "Needs content",
                        } as Record<string, string>
                      )[s.state || "saved"]
                    }
                  </span>
                  {s.state === "needs_content" && (
                    <>
                      <p>{s.reason}</p>
                      <button
                        onClick={() => {
                          resumeUpload.current = null;
                          fallback.current = s.id;
                          file.current?.click();
                          post("/events", { name: "capture_fallback" }).catch(
                            () => {},
                          );
                        }}
                      >
                        Add screenshots or video
                      </button>
                    </>
                  )}
                  {s.needs_upload && <button onClick={()=>{
                    fallback.current = null; resumeUpload.current = s.id;
                    file.current?.click();
                  }}>Resume upload</button>}
                  <button
                    className="text-button"
                    onClick={async () => {
                      try {
                        setSource(await api("/captures/" + s.id));
                      } catch (e) {
                        report(e);
                      }
                    }}
                  >
                    Details
                  </button>
                </article>
              ))}
            </div>
            {!library.sources.length && (
              <p className="empty">Your next pack starts here.</p>
            )}
            {selected.length > 0 && (
              <div className="assemble-bar">
                <strong>{selected.length} sources →</strong>
                <input
                  aria-label="Pack name"
                  placeholder="Name your pack"
                  value={packName}
                  maxLength={120}
                  onChange={(e) => setPackName(e.target.value)}
                />
                <button
                  className="primary"
                  disabled={
                    busy ||
                    !packName.trim() ||
                    selected.length > config.maxSources
                  }
                  onClick={assemble}
                >
                  Create pack ✦
                </button>
              </div>
            )}
            <h2 className="section-heading">Your packs</h2>
            <div className="pack-grid">
              {library.packs.map((p) => (
                <article className="library-pack" key={p.id}>
                  <Icon name="pack" />
                  <h3>{p.title}</h3>
                  <p>{p.source_count} sources</p>
                  <div className="actions">
                    <button
                      onClick={() => {
                        setChosen(p);
                        setBrief("");
                        setTab("Make");
                        setResult(null);
                      }}
                    >
                      Make something →
                    </button>
                    <button onClick={() => sharePack(p.id)}>Share ↗</button>
                  </div>
                </article>
              ))}
            </div>
            <h2 className="section-heading">Saved creations</h2>
            <div className="result-list">
              {library.results.map((r) => (
                <button
                  key={r.id}
                  onClick={async () => {
                    try {
                      const loaded = await api("/results/" + r.id);
                      setResult(loaded);
                      const p = library.packs.find(
                        (p) => p.id === loaded.pack_id,
                      );
                      if (p) setChosen(p);
                      setTab("Make");
                    } catch (e) {
                      report(e);
                    }
                  }}
                >
                  <span>✦</span>
                  {r.title}
                  <b>↗</b>
                </button>
              ))}
            </div>
          </>
        )}
        {tab === "Sharing" && (
          <>
            <section className="intro">
              <h1>Shared packs.</h1>
              <p>Fixed versions. Revoke a link whenever you need.</p>
            </section>
            {myShares.map((s) => (
              <div className="share-row" key={s.id}>
                <strong>{s.title}</strong>
                <span>{s.revoked ? "Revoked" : "Unlisted link"}</span>
                <button
                  disabled={s.revoked}
                  onClick={async () => {
                    try {
                      await post("/shares/" + s.id + "/revoke");
                      await showShares();
                    } catch (e) {
                      report(e);
                    }
                  }}
                >
                  Revoke link
                </button>
              </div>
            ))}
            <p className="muted">
              Revoking stops access through the link. Copies people already
              added remain theirs.
            </p>
          </>
        )}
        {current && (
          <div className="progress" role="status">
            <span className="spinner" />{" "}
            {library.operations.find((o) => o.id === current)?.kind === "create"
              ? "Making your result…"
              : "Working on your pack…"}
            <button
              onClick={() => post("/jobs/" + current + "/cancel").catch(report)}
            >
              Cancel
            </button>
          </div>
        )}
        {library.operations
          .filter((o) => ["failed", "cancelled"].includes(o.status))
          .slice(0, 2)
          .map((o) => (
            <div className="banner error" key={o.id}>
              {o.error || "Cancelled. Your saved work is safe."}
              <button
                onClick={() => {
                  done.current.delete(o.id);
                  post("/jobs/" + o.id + "/retry")
                    .then((op) => {
                      setCurrent(op.operation_id);
                      setBusy(true);
                    })
                    .catch(report);
                }}
              >
                Retry
              </button>
            </div>
          ))}
      </main>
      <footer>
        <span>Collect → Create → Share → Create again</span>
        <small>Lectic · Invited pilot</small>
      </footer>
      {share && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="share-title"
          >
            <button
              className="close"
              onClick={() => setShare("")}
              aria-label="Close"
            >
              ×
            </button>
            <Icon name="pack" />
            <h2 id="share-title">Pass the pack along.</h2>
            <p>They bring a new idea. Your library stays private.</p>
            <label htmlFor="share-url">Unlisted pack link</label>
            <input id="share-url" value={share} readOnly />
            <button
              className="primary"
              onClick={() =>
                navigator.clipboard
                  .writeText(share)
                  .then(() => setNotice("Link copied"))
                  .catch(report)
              }
            >
              Copy link
            </button>
            <small>
              Anyone with this link can preview this pack. Invited users can
              save a copy.
            </small>
          </section>
        </div>
      )}
      {source && (
        <div className="modal-backdrop">
          <section
            className="modal source-detail"
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-title"
          >
            <button
              className="close"
              onClick={() => setSource(null)}
              aria-label="Close"
            >
              ×
            </button>
            <h2 id="source-title">{source.title}</h2>
            {source.preview?.sources.map((s: any) => (
              <p key={s.id}>
                {s.title} <small>{s.caption_type}</small>
              </p>
            ))}
            {source.data?.url && <p>{source.data.url}</p>}
            {source.data?.reason && <p>{source.data.reason}</p>}
            {source.data?.documents?.map((d: any) => (
              <details key={d.filename}>
                <summary>{d.metadata.title}</summary>
                <div className="prose">{d.text}</div>
              </details>
            ))}
            {source.data?.derivations && (
              <details>
                <summary>Processing & provenance</summary>
                {source.data.derivations.map((d: any, i: number) => (
                  <p key={i}>
                    {d.label || d.kind} · {d.model || "Text extraction"}{" "}
                    {d.reference ? "· " + JSON.stringify(d.reference) : ""}
                  </p>
                ))}
              </details>
            )}
            {source.data?.limitations?.map((l: string) => (
              <p key={l}>{l}</p>
            ))}
          </section>
        </div>
      )}
    </>
  );
}
function SignIn({ login }: { login: (provider: "google" | "apple") => void }) {
  return (
    <div className="sign-in">
      <p>Sign in to make it yours.</p>
      <button className="primary" onClick={() => login("google")}>
        Continue with Google
      </button>
      <button onClick={() => login("apple")}>Continue with Apple</button>
      <small>For invited accounts. Your selected pack will be waiting.</small>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

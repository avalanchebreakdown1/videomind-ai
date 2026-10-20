"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Job, Notes, requestJson, stageLabel, terminal, youtubeUrl } from "../lib/client";

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    play: <><rect x="2" y="5" width="20" height="14" rx="5"/><path d="m10 9 5 3-5 3Z"/></>,
    book: <><path d="M12 6c-3-3-7-3-10-2v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-3-1-7-1-10 2Z"/><path d="M12 6v15"/></>,
    arrow: <><path d="M4 12h16m-6-6 6 6-6 6"/></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v4h16v-4"/></>,
    file: <><path d="M14 2H5v20h14V7Zm0 0v6h5M8 12h8m-8 4h6"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    download: <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>,
    spark: <><path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6Z"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    shield: <><path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6Z"/><path d="m8 12 3 3 5-6"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.file}</svg>;
}

type Health = { status: string; worker_running: boolean; max_upload_bytes: number };
type Recent = { id: string; title: string };
const storageKey = "videomind-recent-jobs";

export default function Home() {
  const [source, setSource] = useState<"youtube" | "audio">("youtube");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [connectionChecked, setConnectionChecked] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [recent, setRecent] = useState<Recent[]>([]);
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [notes, setNotes] = useState<Notes | null>(null);
  const [transcript, setTranscript] = useState("");
  const [preview, setPreview] = useState<"document" | "transcript">("document");
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const epoch = useRef(0);
  const active = busy || Boolean(job && !terminal(job));
  const sourceInput = useRef<HTMLInputElement>(null);
  const results = useRef<HTMLElement>(null);

  const remember = useCallback((value: Job) => {
    const title = value.metadata?.title || value.metadata?.filename || "Educational video";
    setRecent(previous => {
      const updated = [{ id: value.id, title }, ...previous.filter(r => r.id !== value.id)].slice(0, 5);
      try { localStorage.setItem(storageKey, JSON.stringify(updated)); } catch { /* Storage may be disabled. */ }
      return updated;
    });
  }, []);

  const openJob = useCallback(async (id: string) => {
    const token = ++epoch.current;
    setBusy(true); setJob(null); setError(""); setPollError(""); setNotes(null); setTranscript(""); setPreviewError("");
    try {
      const value = await requestJson<Job>(`/api/jobs/${id}`);
      if (token !== epoch.current) return;
      setJob(value); remember(value);
      window.history.replaceState(null, "", `?job=${value.id}`);
    } catch (e) { if (token === epoch.current) setError((e as Error).message); }
    finally { if (token === epoch.current) setBusy(false); }
  }, [remember]);

  useEffect(() => {
    const linked = new URLSearchParams(window.location.search).get("job");
    if (linked && /^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(linked)) {
      void openJob(linked); return;
    }
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
      if (Array.isArray(saved)) {
        const valid = saved.filter(v => typeof v?.id === "string" && /^[\da-f-]{36}$/i.test(v.id) && typeof v.title === "string").slice(0, 5);
        setRecent(valid);
        if (valid.length) void openJob(valid[0].id);
      }
    } catch { /* Ignore corrupt or disabled browser storage. */ }
  }, [openJob]);

  useEffect(() => {
    let stopped = false;
    async function check() {
      try {
        const value = await requestJson<Health>("/api/health");
        if (!stopped) setHealth(value);
      } catch { if (!stopped) setHealth(null); }
      finally { if (!stopped) setConnectionChecked(true); }
    }
    void check(); const timer = setInterval(check, 15000);
    return () => { stopped = true; clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!job || terminal(job)) return;
    const id = job.id; let stopped = false; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const value = await requestJson<Job>(`/api/jobs/${id}`);
        if (stopped) return;
        setJob(value); setPollError("");
        if (terminal(value)) { remember(value); return; }
      } catch (e) { if (!stopped) setPollError((e as Error).message); }
      if (!stopped) timer = setTimeout(poll, 1000);
    }
    timer = setTimeout(poll, 750);
    return () => { stopped = true; clearTimeout(timer); };
  }, [job?.id, job?.state, remember]); // A running job's percentage must not restart the polling loop.

  const rawAvailable = Boolean(job?.artifacts.includes("raw_transcript.json"));
  const documentAvailable = Boolean(job?.artifacts.includes("document.docx") && job.state === "completed");
  useEffect(() => {
    if (!job) return;
    let stopped = false;
    async function load() {
      setPreviewError("");
      try {
        const values = await Promise.all([
          rawAvailable ? requestJson<{ text: string }>(`/api/jobs/${job!.id}/transcript`) : null,
          documentAvailable ? requestJson<Notes>(`/api/jobs/${job!.id}/document?format=json`) : null,
        ]);
        if (!stopped) { if (values[0]) setTranscript(values[0].text); if (values[1]) setNotes(values[1]); }
      } catch (e) { if (!stopped) setPreviewError((e as Error).message); }
    }
    if (rawAvailable || documentAvailable) void load();
    return () => { stopped = true; };
  }, [job?.id, rawAvailable, documentAvailable]);

  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (active) return;
    setError(""); setDownloadError("");
    try {
      if (!authorized) throw new Error("Confirm that you have permission to process this source.");
      const form = new FormData(); form.set("authorized", "true"); form.set("write_document", "true");
      if (source === "youtube") form.set("youtube_url", youtubeUrl(url));
      else {
        if (!file) throw new Error("Choose an audio file to upload.");
        if (file.size === 0) throw new Error("The selected file is empty.");
        if (file.size > (health?.max_upload_bytes || 256 * 1024 * 1024)) throw new Error("This audio file exceeds the upload limit.");
        form.set("file", file);
      }
      const token = ++epoch.current;
      setBusy(true);
      const value = await requestJson<Job>("/api/jobs", { method: "POST", body: form });
      if (token !== epoch.current) return;
      setJob(value); remember(value); setNotes(null); setTranscript(""); setPreviewError(""); setPollError(""); setPreview("document");
      window.history.replaceState(null, "", `?job=${value.id}`);
      results.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function cancel() {
    if (!job || cancelling) return;
    setCancelling(true);
    try { const value = await requestJson<Job>(`/api/jobs/${job.id}/cancel`, { method: "POST" }); setJob(value); }
    catch (e) { setPollError((e as Error).message); }
    finally { setCancelling(false); }
  }

  async function download(kind: "docx" | "txt" | "transcript") {
    if (!job || downloading) return;
    setDownloading(true); setDownloadError("");
    try {
      const path = kind === "transcript" ? `transcript?format=txt&download=true` : `document?format=${kind}`;
      const response = await fetch(`/api/jobs/${job.id}/${path}`, { cache: "no-store" });
      if (!response.ok) { const value = await response.json(); throw new Error(value?.error?.message || "The download failed. Please try again."); }
      const blob = await response.blob(); const object = URL.createObjectURL(blob); const a = document.createElement("a");
      a.href = object; a.download = `videomind-${job.id}-${kind === "transcript" ? "transcript.txt" : `notes.${kind}`}`;
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(object), 1000);
    } catch (e) { setDownloadError((e as Error).message || "The download failed. Try again."); }
    finally { setDownloading(false); }
  }

  function newProject() {
    if (active) return;
    ++epoch.current; setJob(null); setNotes(null); setTranscript(""); setError(""); setPreviewError(""); setDownloadError("");
    setUrl(""); setFile(null); setAuthorized(false); sourceInput.current?.focus();
    window.history.replaceState(null, "", window.location.pathname);
  }

  const jobTitle = job?.metadata?.title || job?.metadata?.filename || "Your educational video";
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="VideoMind AI home"><span className="brand-mark"><Icon name="book" size={23}/></span><span>VideoMind<span className="brand-ai">AI</span></span></a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <button className="nav-item selected" onClick={() => results.current?.scrollIntoView({ behavior: "smooth" })}><Icon name="spark"/> Create study notes <span className="nav-dot"/></button>
      <button className="new-project" onClick={newProject} disabled={active}><Icon name="plus" size={17}/> New source</button>
      <div className="recent-label">RECENT SOURCES <span>{recent.length.toString().padStart(2, "0")}</span></div>
      <nav className="recent-list" aria-label="Recent sources">{recent.length ? recent.map(r => <button key={r.id} disabled={active || busy} title={r.title} onClick={() => void openJob(r.id)} className={job?.id === r.id ? "recent active" : "recent"}><Icon name="file" size={16}/><span>{r.title}</span></button>) : <p>Your sources will appear here.<br/>Pick up where you left off.</p>}</nav>
      <div className="sidebar-note"><span className="tiny-icon"><Icon name="shield" size={18}/></span><strong>Your own learning space</strong><p>Processing and saved files stay on this computer.</p></div>
      <div className="profile"><span className="avatar">Y</span><div><strong>Your workspace</strong><small>Local edition</small></div><span className="local-badge">LOCAL</span></div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><span>Workspace <span className="breadcrumb">/</span> <strong>Create study notes</strong></span><span className={`connection ${health?.worker_running ? "online" : ""}`} role="status"><i/>{health?.worker_running ? "Ready to process" : connectionChecked ? "Service unavailable" : "Connecting…"}</span></header>
      <main>
        <section className="intro"><div className="eyebrow"><span/> LESS REWATCHING. MORE UNDERSTANDING.</div><h1>Good ideas deserve<br/><span>a place to stay.</span></h1><p>Turn an educational video into a clear transcript and<br className="desktop-br"/> focused study notes you can make your own.</p></section>
        <div className="workflow" aria-label="Workflow"><span className={!job ? "current" : "done"}><b>{job ? <Icon name="check" size={13}/> : "1"}</b>Add your source</span><i/><span className={job && !terminal(job) ? "current" : documentAvailable ? "done" : ""}><b>{documentAvailable ? <Icon name="check" size={13}/> : "2"}</b>Let it take shape</span><i/><span className={documentAvailable ? "current" : ""}><b>3</b>Read & keep</span></div>

        <section className="source-card" aria-labelledby="source-heading">
          <div className="card-heading"><div><h2 id="source-heading">What are we learning today?</h2><p>Start with a single video or an audio recording.</p></div><span className="card-icon"><Icon name="play" size={25}/></span></div>
          <div className="source-tabs" role="tablist" aria-label="Source type"><button role="tab" aria-selected={source === "youtube"} disabled={active} onClick={() => { setSource("youtube"); setError(""); }}><Icon name="play" size={17}/>YouTube link</button><button role="tab" aria-selected={source === "audio"} disabled={active} onClick={() => { setSource("audio"); setError(""); }}><Icon name="upload" size={17}/>Audio file</button></div>
          <form onSubmit={submit}>
            {source === "youtube" ? <div className="input-group"><label htmlFor="youtube-url">YouTube video URL</label><div className="url-field"><Icon name="play"/><input ref={sourceInput} id="youtube-url" type="url" placeholder="https://www.youtube.com/watch?v=…" value={url} onChange={e => setUrl(e.target.value)} disabled={active} required aria-describedby="source-hint"/></div><p id="source-hint" className="input-hint">A lecture, a lesson, a new perspective. One video at a time.</p></div> : <div className="input-group"><label htmlFor="audio-file">Audio recording</label><div className="upload-field"><Icon name="upload" size={24}/><input id="audio-file" type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg,.flac,.webm" onChange={e => setFile(e.target.files?.[0] || null)} disabled={active}/><span>{file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB` : `Choose an audio file · up to ${Math.floor((health?.max_upload_bytes || 268435456) / 1024 / 1024)} MB`}</span></div><p className="input-hint">Useful when a video cannot be downloaded.</p></div>}
            <label className="authorization"><input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} disabled={active}/><span>I have permission to download and process this source.</span></label>
            {error && <div className="error-message" role="alert">{error}</div>}
            {connectionChecked && !health?.worker_running && <div className="service-notice">The processing service is unavailable. Start the backend, then try again.</div>}
            <div className="form-bottom"><span><Icon name="file" size={16}/>Transcript + study document</span><button className="primary-button" type="submit" disabled={active || (connectionChecked && !health?.worker_running)}>{busy ? "Submitting…" : job && !terminal(job) ? "Processing…" : "Create my notes"}<Icon name="arrow" size={18}/></button></div>
          </form>
        </section>

        {job ? <section className="results-card" ref={results} aria-label="Processing results">
          <div className="result-title"><span className={`result-symbol ${job.state}`}><Icon name={documentAvailable ? "check" : "clock"}/></span><div><h2>{stageLabel(job.stage)}</h2><p title={jobTitle}>{jobTitle}</p></div>{!terminal(job) && <button className="text-button" onClick={() => void cancel()} disabled={cancelling || job.cancel_requested}>{job.cancel_requested ? "Cancelling…" : "Cancel"}</button>}</div>
          {!terminal(job) && <><div className="progress-label"><span>{job.cancel_requested ? "Stopping after the current operation…" : stageLabel(job.stage)}</span><b>{job.progress}%</b></div><div className="progress-track" role="progressbar" aria-label="Processing progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress}><div style={{ width: `${job.progress}%` }}/></div><p className="processing-hint">You can leave this page and return. Processing continues locally.</p></>}
          {job.error && <div role="alert" className="error-message">{job.error.message}{rawAvailable && " Your original transcript is still available below."}</div>}
          {job.state === "cancelled" && <div className="service-notice">This job was cancelled. Add a source to start a new one.</div>}
          {pollError && <div role="alert" className="error-message">{pollError} We’ll keep trying to reconnect.</div>}
          <div className="preview-toolbar"><div className="preview-tabs" role="tablist" aria-label="Output preview"><button role="tab" aria-selected={preview === "document"} onClick={() => setPreview("document")}><Icon name="book" size={16}/>Study notes</button><button role="tab" aria-selected={preview === "transcript"} onClick={() => setPreview("transcript")}><Icon name="file" size={16}/>Transcript</button></div><span className="draft-label">{documentAvailable ? "AI-generated draft" : "Preview"}</span></div>
          {previewError && <div className="error-message" role="alert">{previewError}<button className="text-button" onClick={() => void openJob(job.id)}>Reload preview</button></div>}
          <div className="preview-area" role="tabpanel" aria-label={preview === "document" ? "Study notes preview" : "Transcript preview"}>
            {preview === "document" ? notes ? <article className="document-preview"><div className="document-kicker">YOUR STUDY NOTES</div><h3>{notes.title}</h3>{notes.sections.map((s, i) => <section key={i}><h4>{s.heading}</h4>{(s.blocks || s.paragraphs?.map(p => ({ kind: "paragraph", text: p.text })) || []).map((b, j) => b.kind === "code" ? <pre key={j}><code>{b.text}</code></pre> : <p key={j}>{b.text}</p>)}</section>)}</article> : <div className="empty-preview"><Icon name="book" size={30}/><strong>{job.state === "failed" ? "The document could not be created" : "Your notes will appear here"}</strong><span>{job.state === "failed" ? "Review the error above, or download the available transcript." : "We’ll organize the important explanations into a document."}</span></div> : transcript ? <div className="transcript-preview"><span className="document-kicker">ORIGINAL TRANSCRIPT</span><p>{transcript}</p></div> : <div className="empty-preview"><Icon name="file" size={30}/><strong>Your transcript will appear here</strong><span>It becomes available as soon as transcription finishes.</span></div>}
          </div>
          {(documentAvailable || rawAvailable) && <div className="download-bar"><div><strong>Take your learning with you.</strong><small>{documentAvailable ? "Review the generated notes before sharing or teaching." : "Your original transcript is preserved."}</small></div><div className="download-actions">{documentAvailable && <><button className="download-button" disabled={downloading} onClick={() => void download("txt")}><Icon name="download" size={16}/>Notes TXT</button><button className="primary-button small" disabled={downloading} onClick={() => void download("docx")}><Icon name="download" size={16}/>Download Word</button></>}{rawAvailable && <button className="text-button" disabled={downloading} onClick={() => void download("transcript")}>Transcript TXT</button>}</div></div>}
          {downloadError && <div className="error-message" role="alert">{downloadError}</div>}
        </section> : <section className="benefits"><div><span className="benefit-icon peach"><Icon name="play"/></span><h3>Bring the source</h3><p>Paste an educational video<br/>or upload your audio.</p></div><div><span className="benefit-icon lavender"><Icon name="spark"/></span><h3>Keep what matters</h3><p>Clear explanations, useful examples.<br/>Less chatter to read through.</p></div><div><span className="benefit-icon mint"><Icon name="book"/></span><h3>Make it yours</h3><p>Read, revisit, and download<br/>your notes as Word or text.</p></div></section>}
        <footer className="main-footer"><span><Icon name="shield" size={14}/> Local processing. Original transcript preserved.</span><span>Made for a curious mind.</span></footer>
      </main>
    </div>
  </div>;
}

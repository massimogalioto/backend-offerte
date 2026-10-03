"use client";

import { useEffect, useRef, useState } from "react";
import { Item, runBatch, selectPdfs } from "./cte-batch";
import { CheckCircle2, FileText, FolderOpen, LoaderCircle, RotateCcw, UploadCloud } from "lucide-react";

// baseUrl must point to an authenticated same-origin server proxy, never carry API keys.
export default function CaricamentoMassivoCTE({ baseUrl = "/api/service", onRunningChange }: { baseUrl?: string; onRunningChange?: (running: boolean) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const lock = useRef(false);
  const [items, setItems] = useState<Item[]>([]);
  const [running, setRunning] = useState(false);
  const [selected, setSelected] = useState(false);
  const completed = items.filter(item => item.status === "COMPLETATA").length;
  const errors = items.filter(item => item.status === "ERRORE").length;
  const finished = completed + errors;

  useEffect(() => {
    if (!running) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [running]);

  async function start(retry = false) {
    if (lock.current) return;
    lock.current = true; setRunning(true); onRunningChange?.(true);
    const queue = items.filter(item => item.status === (retry ? "ERRORE" : "IN ATTESA"));
    setItems(current => current.map(item => queue.some(entry => entry.id === item.id) ? { ...item, status: "IN ATTESA", error: null } : item));
    try {
      await runBatch(queue, baseUrl.replace(/\/$/, ""), (id, patch) => {
        setItems(current => current.map(item => item.id === id ? { ...item, ...patch } : item));
      });
    } finally { lock.current = false; setRunning(false); onRunningChange?.(false); }
  }

  return <section aria-labelledby="massivo-cte-title">
    <div className="batch-heading"><div><span className="panel-number">PIÙ DOCUMENTI, UN SOLO FLUSSO</span><h2 id="massivo-cte-title">Caricamento massivo CTE</h2><p className="muted">Seleziona una cartella: elaboriamo soltanto i PDF e salviamo automaticamente le offerte.</p></div><span className="batch-concurrency"><span className="cyan-dot" /> 2 file alla volta</span></div>
    <input ref={input} type="file" multiple accept=".pdf" {...{ webkitdirectory: "", directory: "" }} hidden
      disabled={running} onChange={event => {
        setItems(selectPdfs(Array.from(event.target.files ?? []))); setSelected(true);
        event.target.value = "";
      }} />
    <button className="upload-zone folder-zone" disabled={running} onClick={() => input.current?.click()}><span className="upload-symbol"><FolderOpen size={30} /></span><strong>Seleziona cartella CTE</strong><span>I file JPG, TXT e gli altri formati vengono ignorati.</span><small>PDF · Fino a 25 MB per file</small></button>
    <div className="batch-toolbar"><strong>CTE trovate: <span className="amber-text">{items.length}</span></strong><div><button className="button outline" disabled={running || !errors} onClick={() => void start(true)}><RotateCcw size={16} /> Riprova errori</button><button className="button primary" disabled={running || !items.some(item => item.status === "IN ATTESA")} onClick={() => void start()}>{running ? <LoaderCircle className="spin" size={17} /> : <UploadCloud size={17} />} ELABORA TUTTE LE CTE</button></div></div>
    {selected && !items.length && <p className="alert">Nessun PDF presente nella cartella selezionata.</p>}
    {items.length > 0 && <><div className="batch-progress"><p aria-live="polite">{completed} / {items.length} completate <span>{finished} terminate · {errors} errori</span></p><progress value={finished} max={items.length || 1} aria-label="Avanzamento CTE" /></div>
    <ul className="batch-list">{items.map((item, index) => <li key={item.id}>
      <span className="file-row-icon">{item.success ? <CheckCircle2 size={20} /> : <FileText size={20} />}</span><div className="file-row-name"><strong>{item.file.webkitRelativePath || item.filename}</strong><small>Documento {index + 1} di {items.length}{item.airtable_id ? ` · ${item.airtable_id}` : ""}</small>{item.error && <p className="file-error" role="alert">{item.error}</p>}</div><span className="status-badge" data-state={item.status}>{(item.status === "ELABORAZIONE" || item.status === "SALVATAGGIO") && <LoaderCircle size={12} className="spin" />}{item.status}</span>
    </li>)}</ul></>}
    {!running && items.length > 0 && finished === items.length && <div className={`alert ${errors ? "" : "success"}`} role="status">Totale: {items.length} — Completate: {completed} — Errori: {errors}</div>}
    <p className="form-note">La fonte CTE viene impostata con il nome originale del file. Mantieni aperta questa pagina durante l’elaborazione.</p>
  </section>;
}

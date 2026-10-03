"use client";
import { ChangeEvent, useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";

export default function UploadZone({ file, onChange, disabled = false, label = "Trascina qui il tuo PDF" }: { file: File | null; onChange: (file: File | null) => void; disabled?: boolean; label?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  function select(files: File[]) {
    setError("");
    if (files.length !== 1) { setError("Seleziona un solo PDF alla volta."); return; }
    const chosen = files[0];
    if (!/\.pdf$/i.test(chosen.name)) { setError("Sono accettati soltanto file PDF."); return; }
    if (!chosen.size || chosen.size > 25 * 1024 * 1024) { setError("Il PDF deve avere una dimensione compresa tra 1 byte e 25 MB."); return; }
    onChange(chosen);
  }
  function changed(event: ChangeEvent<HTMLInputElement>) { if (event.target.files?.length) select(Array.from(event.target.files)); event.target.value = ""; }
  return <div>
    <input ref={input} type="file" accept=".pdf" onChange={changed} disabled={disabled} hidden aria-label="Seleziona PDF" />
    <button type="button" className={`upload-zone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`} disabled={disabled} onClick={() => input.current?.click()}
      onDragOver={event => { event.preventDefault(); if (!disabled) setDragging(true); }} onDragLeave={() => setDragging(false)}
      onDrop={event => { event.preventDefault(); setDragging(false); if (!disabled) select(Array.from(event.dataTransfer.files)); }}>
      <span className="upload-symbol">{file ? <FileText size={30} /> : <UploadCloud size={30} />}</span>
      <strong>{file ? file.name : label}</strong>
      <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Clicca per sostituire` : "oppure clicca per scegliere un file"}</span>
      <small>Formato PDF · Fino a 25 MB</small>
    </button>
    {file && !disabled && <button type="button" className="text-button" onClick={() => onChange(null)}><X size={14} /> Rimuovi file</button>}
    {error && <p className="alert error" role="alert">{error}</p>}
  </div>;
}

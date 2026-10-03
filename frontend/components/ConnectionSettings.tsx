"use client";
import { useEffect, useState } from "react";
import { directConnection, readConnection, saveConnection } from "@/lib/connection";

export default function ConnectionSettings() {
  const [url, setUrl] = useState("");
  const [key, setKey] = useState("");
  const [message, setMessage] = useState("");
  const [expanded, setExpanded] = useState(true);
  useEffect(() => { const current = readConnection(); setUrl(current.url); setKey(current.key); setExpanded(!current.url); }, []);
  if (!directConnection) return null;
  return <details className="shell panel" open={expanded} onToggle={event => setExpanded(event.currentTarget.open)}><summary>Collegamento al servizio</summary>
    <form onSubmit={event => { event.preventDefault(); try { saveConnection(url, key); setMessage("Collegamento salvato per questa scheda."); } catch (error) { setMessage(error instanceof Error ? error.message : "Configurazione non valida"); } }}>
      <div className="form-grid"><label>URL backend HTTPS<input type="url" required value={url} placeholder="https://tuo-backend.example.com" onChange={event => setUrl(event.target.value)} /></label>
      <label>Chiave API del backend<input type="password" autoComplete="off" value={key} onChange={event => setKey(event.target.value)} /></label></div>
      <p className="form-note">Usa lo stesso valore di API_SECRET_KEY del backend. Le credenziali restano nella sessione di questa scheda e vengono inviate solo al servizio configurato.</p>
      <button className="button outline" type="submit">Salva collegamento</button><p role="status">{message}</p>
    </form></details>;
}

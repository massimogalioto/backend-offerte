import os
from pyairtable import Table
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import quote
from urllib.parse import urlparse
import base64
import hashlib
import hmac
import json
import logging
import requests

load_dotenv()

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TBL_OFFERTE = os.getenv("AIRTABLE_OFFERTE_TABLE")
TBL_MERCATO = os.getenv("AIRTABLE_MERCATO_TABLE")
logger = logging.getLogger("uvicorn.error")

# Direct Airtable uploadAttachment API limit; no public file hosting is needed.
MAX_CTE_ATTACHMENT_BYTES = 5_000_000


def estrai_cte_attachment(fields):
    attachments = fields.get("CTE")
    if not isinstance(attachments, list):
        return None
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        filename = attachment.get("filename")
        url = attachment.get("url")
        if not isinstance(filename, str) or not isinstance(url, str):
            continue
        if attachment.get("type") != "application/pdf" and not (
            not attachment.get("type") and filename.lower().endswith(".pdf")
        ):
            continue
        try:
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                continue
        except ValueError:
            continue
        return {"filename": filename, "url": url}
    return None


def _cte_retry_signature(record_id, dati, filename, pdf):
    # Bind a retry to its exact record, offer and original PDF, across processes.
    key = API_KEY or os.getenv("API_SECRET_KEY")
    if not key:
        raise ValueError("Credenziali Airtable non configurate")
    digest = hashlib.sha256(pdf).hexdigest()
    payload = json.dumps([record_id, dati, filename, digest], sort_keys=True, ensure_ascii=True)
    return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _upload_cte(table, record_id, filename, pdf):
    upload = getattr(table, "upload_attachment", None)
    if callable(upload):
        return upload(record_id, "CTE", filename, content=pdf, content_type="application/pdf")
    # Compatibility with older pyairtable deployments, using the same env token.
    response = requests.post(
        f"https://content.airtable.com/v0/{quote(BASE_ID, safe='')}/{quote(record_id, safe='')}/CTE/uploadAttachment",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"contentType": "application/pdf", "filename": filename, "file": base64.b64encode(pdf).decode("ascii")},
        timeout=(10, 120),
    )
    response.raise_for_status()
    return response.json()

def get_offerte(tipo_fornitura, tipologia_cliente):
    table = Table(API_KEY, BASE_ID, TBL_OFFERTE)
    oggi = datetime.today()
    mese_corrente = oggi.strftime("%Y-%m")  # esempio: '2025-09'

    formula = f"""AND(
        {{Tipo fornitura}} = '{tipo_fornitura}',
        {{Tipologia cliente}} = '{tipologia_cliente}',
        DATETIME_FORMAT({{Data validità}}, 'YYYY-MM') = '{mese_corrente}'
    )"""
    
    #formula = f"AND({{Tipo fornitura}} = '{tipo_fornitura}', {{Tipologia cliente}} = '{tipologia_cliente}')"
    return table.all(formula=formula)

def get_prezzo_mercato(tipo_fornitura, data_str):
    table = Table(API_KEY, BASE_ID, TBL_MERCATO)
    formula = f"AND({{Tipo fornitura}} = '{tipo_fornitura}', IS_SAME({{Mese}}, DATETIME_PARSE('{data_str}'), 'month'))"
    records = table.all(formula=formula)

    if not records:
        raise Exception(f"Nessun prezzo trovato per {tipo_fornitura} nel mese {data_str}")

    fields = records[0]["fields"]

    prezzo_medio = float(fields.get("Prezzo medio €/kWh", 0))
    disponibilita = float(fields.get("Disp", 0))

    return {
        "prezzo_medio": prezzo_medio,
        "disp": disponibilita
    }
def salva_offerta(dati: dict, pdf: bytes | None = None, filename: str | None = None, cte_retry_token: str | None = None) -> dict:
    try:
        table = Table(API_KEY, BASE_ID, TBL_OFFERTE, timeout=(10, 120)) if pdf is not None else Table(API_KEY, BASE_ID, TBL_OFFERTE)

        record = {
            "Fornitore": dati.get("fornitore"),
            "Nome offerta": dati.get("nome_offerta"),
            "Tipologia cliente": dati.get("tipologia_cliente"),
            "Tipo tariffa": dati.get("tariffa"),
            "Prezzo fisso €/kWh": dati.get("prezzo_kwh"),
            "Spread €/kWh": dati.get("spread"),
            "Costo fisso mensile": dati.get("costo_fisso"),
            "Data validità": dati.get("validita"),
            "Fonte CTE": dati.get("fonte_cte"),
            "Note": dati.get("vincoli"),
            "Tipo fornitura": dati.get("tipo_fornitura")
        }

        if cte_retry_token:
            record_id, separator, signature = cte_retry_token.partition(".")
            if not separator or pdf is None or not hmac.compare_digest(
                signature, _cte_retry_signature(record_id, dati, filename, pdf)
            ):
                return {"errore": "Il retry CTE non corrisponde al PDF e all'offerta originali"}
            risultato = table.get(record_id)
        else:
            risultato = table.create(record)
        if pdf is None:
            return risultato

        record_id = risultato["id"]
        logger.info("[CTE] Record Airtable %s: %s", "recuperato per retry" if cte_retry_token else "creato", record_id)
        # A timeout can arrive after Airtable has already accepted the PDF.
        existing = risultato.get("fields", {}).get("CTE", [])
        if cte_retry_token and isinstance(existing, list) and any(
            isinstance(item, dict) and item.get("filename") == filename and item.get("size") == len(pdf)
            for item in existing
        ):
            return risultato

        reason = None
        if len(pdf) > MAX_CTE_ATTACHMENT_BYTES:
            reason = "Il PDF supera il limite di 5 MB dell'API uploadAttachment Airtable"
        else:
            try:
                _upload_cte(table, record_id, filename, pdf)
            except Exception as error:
                # Do not expose provider bodies, URLs or authorization headers.
                response = getattr(error, "response", None)
                reason = f"HTTP {response.status_code}" if response is not None else type(error).__name__
        if reason:
            logger.error("[CTE] Upload attachment fallito: %s - %s", filename, reason)
            return {
                "errore": f"Upload attachment fallito: {filename} - {reason}. Record Airtable conservato: {record_id}",
                "id": record_id,
                "fase": "attachment",
                "cte_retry_token": f"{record_id}.{_cte_retry_signature(record_id, dati, filename, pdf)}",
            }
        logger.info("[CTE] Attachment caricato: %s - %s", filename, record_id)
        return risultato

    except Exception as e:
        return {"errore": str(e) if pdf is None else f"Salvataggio CTE Airtable fallito: {type(e).__name__}"}

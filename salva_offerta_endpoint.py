from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from airtable_service import salva_offerta
import logging
import base64
import binascii

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

class CtePdfInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=35_000_000)

class OffertaInput(BaseModel):
    fornitore: str
    nome_offerta: str
    tipologia_cliente: str
    tariffa: str
    prezzo_kwh: float | None = None
    spread: float | None = None
    costo_fisso: float | None = None
    validita: str | None = None
    fonte_cte: str | None = None
    vincoli: str | None = None
    tipo_fornitura: str
    cte_pdf: CtePdfInput | None = None
    cte_retry_token: str | None = Field(default=None, max_length=200)

@router.post("/salva-offerta", summary="Salva un'offerta CTE in Airtable")
def salva(offerta: OffertaInput, x_api_key: str = Header(None)):
    from os import getenv
    if x_api_key != getenv("API_SECRET_KEY"):
        raise HTTPException(status_code=401, detail="Chiave API non valida")

    dati = offerta.dict(exclude={"cte_pdf", "cte_retry_token"})
    if offerta.cte_pdf:
        filename = offerta.cte_pdf.filename
        if not filename.lower().endswith(".pdf") or any(character in filename for character in "/\\\r\n"):
            raise HTTPException(status_code=422, detail="Nome PDF CTE non valido")
        try:
            pdf = base64.b64decode(offerta.cte_pdf.content_base64, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(status_code=422, detail="PDF CTE Base64 non valido")
        if not pdf or b"%PDF-" not in pdf[:1024]:
            raise HTTPException(status_code=422, detail="L'allegato CTE deve essere un PDF originale valido")
        risultato = salva_offerta(dati, pdf=pdf, filename=filename, cte_retry_token=offerta.cte_retry_token)
    elif offerta.cte_retry_token:
        raise HTTPException(status_code=422, detail="Il retry attachment richiede il PDF originale")
    else:
        risultato = salva_offerta(dati)
    if "errore" in risultato:
        logger.error("[CTE] ERRORE: %s - salvataggio Airtable fallito", offerta.fonte_cte)
        if risultato.get("fase") == "attachment":
            raise HTTPException(status_code=502, detail={
                "message": risultato["errore"], "fase": "attachment", "record_id": risultato["id"],
                "cte_retry_token": risultato["cte_retry_token"],
            })
        raise HTTPException(status_code=500, detail=risultato["errore"])

    logger.info("[CTE] Airtable salvato: %s - %s", offerta.fonte_cte, risultato.get("id"))
    return {"successo": True, "id": risultato.get("id")}


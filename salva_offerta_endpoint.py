from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from airtable_service import salva_offerta
import logging

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

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

@router.post("/salva-offerta", summary="Salva un'offerta CTE in Airtable")
def salva(offerta: OffertaInput, x_api_key: str = Header(None)):
    from os import getenv
    if x_api_key != getenv("API_SECRET_KEY"):
        raise HTTPException(status_code=401, detail="Chiave API non valida")

    risultato = salva_offerta(offerta.dict())
    if "errore" in risultato:
        logger.error("[CTE] ERRORE: %s - salvataggio Airtable fallito", offerta.fonte_cte)
        raise HTTPException(status_code=500, detail=risultato["errore"])

    logger.info("[CTE] Airtable salvato: %s - %s", offerta.fonte_cte, risultato.get("id"))
    return {"successo": True, "id": risultato.get("id")}


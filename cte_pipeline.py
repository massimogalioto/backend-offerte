"""Shared synchronous CTE pipeline; callers run it outside the event loop."""
import logging
import shutil
from tempfile import TemporaryDirectory
from pathlib import Path

from fastapi import HTTPException
from pdf2image import convert_from_path
import pytesseract
from estrai_dati_cte import estrai_dati_offerta_cte

logger = logging.getLogger("uvicorn.error")


def processa_cte(file):
    filename = file.filename
    logger.info("[CTE] Inizio: %s", filename)
    try:
        with TemporaryDirectory(prefix="cte-") as directory:
            path = Path(directory) / "input.pdf"
            file.file.seek(0)
            with path.open("wb") as target:
                shutil.copyfileobj(file.file, target)
            images = convert_from_path(str(path))
            try:
                text = ""
                for i, image in enumerate(images):
                    page_text = pytesseract.image_to_string(image, lang="ita")
                    if page_text.strip():
                        text += f"\n--- Pagina {i+1} ---\n{page_text}"
            finally:
                for image in images:
                    image.close()
        logger.info("[CTE] OCR completato: %s", filename)
        if not text.strip():
            raise HTTPException(status_code=422, detail="Non è stato possibile estrarre testo dal PDF")
        dati = estrai_dati_offerta_cte(text)
        logger.info("[CTE] AI completata: %s", filename)
        return dati
    except Exception:
        # Provider exceptions can contain credentials/URLs: do not log their text.
        logger.error("[CTE] ERRORE: %s - elaborazione fallita", filename)
        raise
    finally:
        logger.info("[CTE] Fine: %s", filename)

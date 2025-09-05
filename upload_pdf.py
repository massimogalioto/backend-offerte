#modificato (2025-06-02)
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from fastapi.responses import JSONResponse
from tempfile import NamedTemporaryFile
from estrai_dati_bolletta import estrai_dati_bolletta  # ✅ estrae dati bolletta
from estrai_dati_cte import estrai_dati_offerta_cte
from confronto import confronta_offerte
from datetime import date
from pdf2image import convert_from_path  #modificato (2025-06-02)
import pytesseract  #modificato (2025-06-02)
import traceback  # 👈 #nuova modifica (2025-06-04)

def data_oggi_iso():
    return date.today().isoformat()

router = APIRouter()

# 📄 Estrazione testo da CTE usando OCR
@router.post("/upload-cte")
async def upload_cte_pdf(file: UploadFile = File(...), x_api_key: str = Header(None)):
    secret_key = os.getenv("API_SECRET_KEY")
    if secret_key and x_api_key != secret_key:
        raise HTTPException(status_code=401, detail="Chiave API non valida_")
        
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Il file deve essere un PDF")

    try:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
            file.file.seek(0)
            temp.write(file.file.read())
            temp_path = temp.name

        # ✅ Converti PDF in immagini (una per pagina)
        images = convert_from_path(temp_path)

        # ✅ Estrai testo da ogni pagina con Tesseract OCR
        text = ""
        for i, image in enumerate(images):
            page_text = pytesseract.image_to_string(image, lang="ita")
            text += f"\n--- Pagina {i+1} ---\n{page_text}"

        os.remove(temp_path)

        if not text.strip():
            raise HTTPException(status_code=422, detail="Non è stato possibile estrarre testo dal PDF")

        # ✅ Analizza con OpenAI o altra funzione AI
        dati = estrai_dati_offerta_cte(text)

        return {
            "filename": file.filename,
            "output_ai": dati
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'elaborazione: {str(e)}")





# 🧾 Estrazione + confronto da bolletta PDF
@router.post("/upload-bolletta")
async def upload_bolletta(file: UploadFile = File(...), x_api_key: str = Header(None)):
    secret_key = os.getenv("API_SECRET_KEY")
    if secret_key and x_api_key != secret_key:
        raise HTTPException(status_code=401, detail="Chiave API non valida")

    try:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            file.file.seek(0)
            temp_file.write(file.file.read())
            temp_path = temp_file.name

        #modificato (2025-06-02) - OCR SEMPRE ATTIVO
        images = convert_from_path(temp_path)
        testo = ""
        for image in images:
            testo += pytesseract.image_to_string(image, lang='ita')

        os.remove(temp_path)

        if not testo.strip():
            raise HTTPException(status_code=422, detail="Errore: OCR non ha rilevato testo")

        dati = estrai_dati_bolletta(testo)
        if "errore" in dati:
            return {
                "errore": "Estrazione fallita",
                "dettagli": dati.get("output")
            }

        # ✅ Verifica che tutti i campi necessari siano presenti
        campi_obbligatori = [
            "kwh_totali", "mesi_bolletta", "spesa_materia_energia",
            "tipo_fornitura", "tipologia_cliente"
        ]
        mancanti = [campo for campo in campi_obbligatori if campo not in dati or dati[campo] is None]

        if mancanti:
            return {
                "errore": "Campo mancante nella risposta AI",
                "mancanti": mancanti,
                "output_ai": dati
            }

        confronto_input = {
            "kwh_totali": dati["kwh_totali"],
            "mesi_bolletta": dati["mesi_bolletta"],
            "spesa_materia_energia": dati["spesa_materia_energia"],
            "quota_fissa_vendita": dati["quota_fissa_vendita"], #modifica 05-09-2025
            "tipo_fornitura": dati["tipo_fornitura"],
            "tipologia_cliente": dati["tipologia_cliente"],
            "data_riferimento": data_oggi_iso()
        }

        offerte = confronta_offerte(confronto_input)

        return {
            "bolletta": dati,
            "offerte": offerte
        }

    except Exception as e:
        print("❌ Errore interno:", str(e))  # 👈 #nuova modifica (2025-06-04)
        traceback.print_exc()                # 👈 #nuova modifica (2025-06-04)
        raise HTTPException(status_code=500, detail=str(e))

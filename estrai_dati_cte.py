import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def estrai_dati_offerta_cte(testo: str) -> dict:
    try:
        prompt = (
            "Estrai i dati principali dell'offerta luce o gas da questa CTE (Condizione Tecnico Economica) e restituiscili in formato JSON.\n\n"
            "Campi richiesti:\n"
            "- fornitore (es. Enel Energia)\n"
            "- nome_offerta (nome commerciale dell'offerta)\n"
            "- tipologia_cliente (Residenziale o Business)\n"
            "- tariffa (Fisso o Variabile)\n"
            "- prezzo_kwh (considera il prezzo della materia energia sia essa energia elettica o gas solo se tariffa Fisso, es. 0.145) oppure 0\n"
            "- spread (considera il prezzo della materia energia sia essa energia elettrica o gas solo se tariffa Variabile, potresti trovarlo scritto anche come contributo al consumo o parametro alfa es. 0.0135) oppure 0\n"
            "- costo_fisso (potresti trovarlo scritto anche come  commercializzazione o CCV, se l'importo è maggiore di 30 euro dividilo per 12 e mostra il risultato)\n"
            "- validita (data in formato 'YYYY-MM-DD', oppure se non disponibile aggiungi 3 mesi alla data di caricamento)\n"
            "- vincoli (es. 'Durata minima 12 mesi') o null\n"
            "- tipo_fornitura (Luce o Gas se sono presenti tutti e due scegli sempre solo LUCE)\n\n"
            "Rispondi solo con JSON valido, senza commenti o testo extra. Ecco il testo da analizzare:\n\n"
            "Testo da analizzare:\n"
            f"{testo[:7000]}"
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Sei un assistente esperto in offerte luce e gas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=600
        )

        content = response.choices[0].message.content

        # Rimuove eventuali blocchi markdown tipo ```json
        json_text = re.sub(r"```json|```", "", content).strip()

        return json.loads(json_text)

    except Exception as e:
        return {
            "errore": "Formato non riconosciuto o parsing fallito",
            "output": content if 'content' in locals() else str(e)
        }

import os
from pyairtable import Table
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import quote

load_dotenv()

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TBL_OFFERTE = os.getenv("AIRTABLE_OFFERTE_TABLE")
TBL_MERCATO = os.getenv("AIRTABLE_MERCATO_TABLE")

def get_offerte(tipo_fornitura):
    table = Table(API_KEY, BASE_ID, TBL_OFFERTE)
    return table.all(formula=f"{{Tipo fornitura}} = '{tipo_fornitura}'")

def get_prezzo_mercato(tipo_fornitura, data_str):
    table = Table(API_KEY, BASE_ID, TBL_MERCATO)
    formula = f"AND({{Tipo fornitura}} = '{tipo_fornitura}', IS_SAME({{Mese}}, DATETIME_PARSE('{data_str}'), 'month'))"
    records = table.all(formula=formula)

    if not records:
        raise Exception(f"Nessun prezzo trovato per {tipo_fornitura} nel mese {data_str}")

    return float(records[0]["fields"].get("Prezzo medio €/kWh", 0))

def salva_offerta(dati: dict) -> dict:
    try:
        table = Table(API_KEY, BASE_ID, TBL_OFFERTE)

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

        return table.create(record)

    except Exception as e:
        return {"errore": str(e)}

from airtable_service import get_offerte, get_prezzo_mercato
from datetime import datetime

def confronta_offerte(bolletta):
    # Estrai dati dalla bolletta
    kwh_totali = bolletta.kwh_totali
    mesi_bolletta = bolletta.mesi_bolletta
    spesa_materia_energia = bolletta.spesa_materia_energia
    tipo_fornitura = bolletta.tipo_fornitura
    data = bolletta.data_riferimento

    # Calcoli mensili
    kwh_mensili = kwh_totali / mesi_bolletta
    spesa_mensile = spesa_materia_energia / mesi_bolletta
    prezzo_effettivo = spesa_mensile / kwh_mensili

    offerte = get_offerte(tipo_fornitura)
    prezzo_mercato = get_prezzo_mercato(tipo_fornitura, data)

    confronti = []

    for offerta in offerte:
        fields = offerta.get("fields", {})
        tipo_tariffa = fields.get("Tipo tariffa")
        costo_fisso = fields.get("Costo fisso mensile", 0)

        if tipo_tariffa == "Fisso":
            prezzo_kwh = fields.get("Prezzo fisso €/kWh", 0)
        elif tipo_tariffa == "Variabile":
            spread = fields.get("Spread €/kWh", 0)
            prezzo_kwh = prezzo_mercato + spread
        else:
            continue

        # Calcolo del costo stimato
        costo_stimato = round(prezzo_kwh * kwh_mensili + costo_fisso, 2)
        delta = costo_stimato - spesa_mensile

        if delta < 0:
            tipo_diff = "Risparmio"
            percentuale = abs(delta) / spesa_mensile * 100
        else:
            tipo_diff = "Spesa in più"
            percentuale = delta / spesa_mensile * 100

        confronti.append({
            "fornitore": fields.get("Fornitore"),
            "nome_offerta": fields.get("Nome offerta"),
            "tariffa": tipo_tariffa,
            "prezzo_kwh": round(prezzo_kwh, 4),
            "costo_fisso": costo_fisso,
            "totale_simulato": costo_stimato,
            "prezzo_effettivo_pagato": round(prezzo_effettivo, 4),
            "differenza_€/mese": round(delta, 2),
            "tipo_differenza": tipo_diff,
            "percentuale": round(percentuale, 2)
        })

    confronti.sort(key=lambda x: x["totale_simulato"])
    return confronti

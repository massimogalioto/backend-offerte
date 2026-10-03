"""Attachment contracts, original PDF bytes and unchanged comparison calculations."""
import base64
import importlib.util
import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from fastapi import HTTPException
import airtable_service as airtable
import salva_offerta_endpoint as endpoint

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("attachment_comparison", ROOT / "confronto.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
PDF = b"%PDF-1.4\noriginal test CTE bytes\n%%EOF"
OFFER = dict(fornitore="Edison", nome_offerta="Dynamic", tipologia_cliente="Residenziale", tariffa="Fisso", tipo_fornitura="Luce", fonte_cte="test_edison.pdf")


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.table = Mock()
        self.table.create.return_value = {"id": "recAAAA", "fields": {}}
        self.table.upload_attachment.return_value = {"id": "recAAAA", "fields": {"CTE": [{"filename": "test_edison.pdf"}]}}
        self.table_patch = patch.object(airtable, "Table", return_value=self.table)
        self.table_patch.start()
        self.key_patch = patch.object(airtable, "API_KEY", "test-private-key")
        self.key_patch.start()
        self.addCleanup(self.table_patch.stop)
        self.addCleanup(self.key_patch.stop)

    def test_single_saves_original_bytes_to_same_record(self):
        offer = endpoint.OffertaInput(**OFFER, cte_pdf={"filename": "test_edison.pdf", "content_base64": base64.b64encode(PDF).decode()})
        with patch.dict("os.environ", {"API_SECRET_KEY": "test"}):
            self.assertEqual(endpoint.salva(offer, "test"), {"successo": True, "id": "recAAAA"})
        self.table.upload_attachment.assert_called_once_with("recAAAA", "CTE", "test_edison.pdf", content=PDF, content_type="application/pdf")
        fields = self.table.create.call_args.args[0]
        self.assertEqual(fields["Nome offerta"], "Dynamic")
        self.assertNotIn("cte_pdf", fields)
        self.assertNotIn("CTE", fields)  # no local path or fabricated URL

    def test_three_files_each_attach_to_own_record(self):
        self.table.create.side_effect = [{"id": f"rec{i}", "fields": {}} for i in range(3)]
        for i in range(3):
            pdf = PDF + str(i).encode()
            result = airtable.salva_offerta({**OFFER, "nome_offerta": f"Offer{i}"}, pdf, f"file{i}.pdf")
            self.assertEqual(result["id"], f"rec{i}")
            self.assertEqual(self.table.upload_attachment.call_args.args, (f"rec{i}", "CTE", f"file{i}.pdf"))
            self.assertEqual(self.table.upload_attachment.call_args.kwargs["content"], pdf)

    def test_attachment_failure_keeps_record_and_retry_does_not_create_another(self):
        self.table.upload_attachment.side_effect = requests.Timeout("must never expose private test token")
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            failed = airtable.salva_offerta(OFFER, PDF, "test_edison.pdf")
        self.assertEqual(failed["fase"], "attachment")
        self.assertEqual(failed["id"], "recAAAA")
        self.assertIn("Record Airtable creato: recAAAA", " ".join(logs.output))
        self.assertIn("Upload attachment fallito: test_edison.pdf - Timeout", " ".join(logs.output))
        self.assertNotIn("private test token", str(failed) + str(logs.output))
        self.table.delete.assert_not_called()
        self.table.get.return_value = {"id": "recAAAA", "fields": {}}
        self.table.upload_attachment.side_effect = None
        result = airtable.salva_offerta(OFFER, PDF, "test_edison.pdf", failed["cte_retry_token"])
        self.assertEqual(result["id"], "recAAAA")
        self.assertEqual(self.table.create.call_count, 1)

    def test_retry_cannot_attach_another_pdf_or_offer_to_record(self):
        self.table.upload_attachment.side_effect = requests.Timeout()
        failed = airtable.salva_offerta(OFFER, PDF, "test_edison.pdf")
        calls = self.table.upload_attachment.call_count
        for offer, pdf, name in [({**OFFER, "nome_offerta": "Other"}, PDF, "test_edison.pdf"), (OFFER, PDF + b"changed", "test_edison.pdf"), (OFFER, PDF, "other.pdf")]:
            result = airtable.salva_offerta(offer, pdf, name, failed["cte_retry_token"])
            self.assertIn("errore", result)
        self.assertEqual(self.table.upload_attachment.call_count, calls)
        self.assertEqual(self.table.create.call_count, 1)

    def test_retry_after_upload_timeout_recognizes_existing_attachment(self):
        self.table.upload_attachment.side_effect = requests.Timeout()
        failed = airtable.salva_offerta(OFFER, PDF, "test_edison.pdf")
        self.table.get.return_value = {"id": "recAAAA", "fields": {"CTE": [{"filename": "test_edison.pdf", "size": len(PDF)}]}}
        result = airtable.salva_offerta(OFFER, PDF, "test_edison.pdf", failed["cte_retry_token"])
        self.assertEqual(result["id"], "recAAAA")
        self.assertEqual(self.table.upload_attachment.call_count, 1)
        self.assertEqual(self.table.create.call_count, 1)

    def test_legacy_json_saves_without_attachment(self):
        result = airtable.salva_offerta(OFFER)
        self.assertEqual(result["id"], "recAAAA")
        self.table.upload_attachment.assert_not_called()

    def test_attachment_error_returns_record_and_retry_token_to_frontend(self):
        self.table.upload_attachment.side_effect = requests.Timeout()
        offer = endpoint.OffertaInput(**OFFER, cte_pdf={"filename": "test_edison.pdf", "content_base64": base64.b64encode(PDF).decode()})
        with patch.dict("os.environ", {"API_SECRET_KEY": "test"}), self.assertRaises(HTTPException) as error:
            endpoint.salva(offer, "test")
        self.assertEqual(error.exception.status_code, 502)
        self.assertEqual(error.exception.detail["record_id"], "recAAAA")
        self.assertEqual(error.exception.detail["fase"], "attachment")

    def test_rejects_invalid_pdf_and_unauthorized_upload_before_create(self):
        with patch.dict("os.environ", {"API_SECRET_KEY": "test"}):
            for data in ["not base64", base64.b64encode(b"not a pdf").decode()]:
                offer = endpoint.OffertaInput(**OFFER, cte_pdf={"filename": "test.pdf", "content_base64": data})
                with self.assertRaises(HTTPException) as error:
                    endpoint.salva(offer, "test")
                self.assertEqual(error.exception.status_code, 422)
            with self.assertRaises(HTTPException) as error:
                endpoint.salva(endpoint.OffertaInput(**OFFER), "wrong")
            self.assertEqual(error.exception.status_code, 401)
        self.table.create.assert_not_called()

    def test_large_attachment_has_identifiable_error_and_keeps_record(self):
        result = airtable.salva_offerta(OFFER, b"x" * (airtable.MAX_CTE_ATTACHMENT_BYTES + 1), "large.pdf")
        self.assertEqual(result["id"], "recAAAA")
        self.assertIn("5 MB", result["errore"])
        self.table.upload_attachment.assert_not_called()

    def test_old_library_fallback_uses_real_content_endpoint_and_base64(self):
        self.table.upload_attachment = None
        response = Mock()
        response.json.return_value = {"id": "recAAAA", "fields": {"CTE": []}}
        with patch.object(airtable, "BASE_ID", "appTest"), patch.object(airtable.requests, "post", return_value=response) as post:
            airtable.salva_offerta(OFFER, PDF, "test_edison.pdf")
        self.assertEqual(post.call_args.args[0], "https://content.airtable.com/v0/appTest/recAAAA/CTE/uploadAttachment")
        self.assertEqual(base64.b64decode(post.call_args.kwargs["json"]["file"]), PDF)
        self.assertEqual(post.call_args.kwargs["json"]["filename"], "test_edison.pdf")

    def test_attachment_metadata_safely_handles_missing_empty_and_non_pdf(self):
        for value in [None, [], "invalid", [None], [{"filename": "image.png", "type": "image/png", "url": "https://example.com/image.png"}], [{"filename": "file.pdf", "url": "javascript:alert(1)"}], [{"filename": "file.pdf", "url": "https://user:password@example.com/file.pdf"}]]:
            self.assertIsNone(airtable.estrai_cte_attachment({"CTE": value}))
        self.assertIsNone(airtable.estrai_cte_attachment({}))
        self.assertEqual(airtable.estrai_cte_attachment({"CTE": [{"filename": "file.pdf", "url": "https://example.com/file.pdf", "type": "application/pdf"}]}), {"filename": "file.pdf", "url": "https://example.com/file.pdf"})

    def test_comparison_matches_git_baseline_and_keeps_each_specific_attachment(self):
        fixed = {"id": "recFIXED", "fields": {"id_offerta": 7, "Fornitore": "Same supplier", "Nome offerta": "Fixed", "Tipo tariffa": "Fisso", "Prezzo fisso €/kWh": 0.12, "Costo fisso mensile": 12, "CTE": [{"filename": "fixed.pdf", "url": "https://example.com/fixed.pdf", "type": "application/pdf"}]}}
        variable = {"id": "recVARIABLE", "fields": {"id_offerta": 8, "Fornitore": "Same supplier", "Nome offerta": "Variable", "Tipo tariffa": "Variabile", "Spread €/kWh": 0.03, "Costo fisso mensile": 18, "CTE": [{"filename": "variable.pdf", "url": "https://example.com/variable.pdf", "type": "application/pdf"}]}}
        without = {"id": "recNOCTE", "fields": {"id_offerta": 9, "Fornitore": "Same supplier", "Nome offerta": "No PDF", "Tipo tariffa": "Fisso", "Prezzo fisso €/kWh": 0.2, "Costo fisso mensile": 10}}
        records = [fixed, variable, without]
        bill = dict(kwh_totali=1200, mesi_bolletta=2, spesa_materia_energia=300, quota_fissa_vendita=24, tipo_fornitura="Luce", tipologia_cliente="Residenziale", data_riferimento="2026-10-03")
        # Freeze the pre-change implementation from Git, without changing files.
        baseline = {}
        source = subprocess.check_output(["git", "show", "cbbd10e:confronto.py"], cwd=ROOT).decode("utf-8")
        exec(compile(source, "baseline-confronto.py", "exec"), baseline)
        baseline["get_offerte"] = Mock(return_value=records)
        baseline["get_prezzo_mercato"] = Mock(return_value={"prezzo_medio": 0.1, "disp": 0.02})
        expected = baseline["confronta_offerte"](bill)
        with patch.object(comparison, "get_offerte", return_value=records) as get, patch.object(comparison, "get_prezzo_mercato", return_value={"prezzo_medio": 0.1, "disp": 0.02}):
            actual = comparison.confronta_offerte(bill)
        get.assert_called_once_with("Luce", "Residenziale")
        self.assertEqual([{key: value for key, value in result.items() if key != "cte"} for result in actual], expected)
        by_name = {result["nome_offerta"]: result["cte"] for result in actual}
        self.assertEqual(by_name["Fixed"]["url"], "https://example.com/fixed.pdf")
        self.assertEqual(by_name["Variable"]["url"], "https://example.com/variable.pdf")
        self.assertIsNone(by_name["No PDF"])


if __name__ == "__main__":
    unittest.main()

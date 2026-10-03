"""Offline tests: no OCR binaries, provider keys or network calls required."""
import asyncio
import importlib
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Avoid initializing the AI client while importing the shared pipeline.
ai = types.ModuleType("estrai_dati_cte")
ai.estrai_dati_offerta_cte = Mock(return_value={"nome_offerta": "Test"})
sys.modules["estrai_dati_cte"] = ai
pipeline = importlib.import_module("cte_pipeline")


class PipelineTests(unittest.TestCase):
    def test_airtable_endpoint_preserves_payload_and_response(self):
        save = importlib.import_module("salva_offerta_endpoint")
        offer = save.OffertaInput(fornitore="Test", nome_offerta="Test", tipologia_cliente="Residenziale", tariffa="Fisso", tipo_fornitura="Luce", fonte_cte="offerta.pdf")
        with patch.dict("os.environ", {"API_SECRET_KEY": "test"}), patch.object(save, "salva_offerta", return_value={"id": "rec-test"}) as airtable:
            self.assertEqual(save.salva(offer, "test"), {"successo": True, "id": "rec-test"})
            self.assertEqual(airtable.call_args.args[0]["fonte_cte"], "offerta.pdf")
            with self.assertRaises(pipeline.HTTPException) as error:
                save.salva(offer, "wrong")
            self.assertEqual(error.exception.status_code, 401)
            self.assertEqual(airtable.call_count, 1)

    def test_airtable_endpoint_reports_failed_save(self):
        save = importlib.import_module("salva_offerta_endpoint")
        offer = save.OffertaInput(fornitore="Test", nome_offerta="Test", tipologia_cliente="Business", tariffa="Variabile", tipo_fornitura="Gas", fonte_cte="failed.pdf")
        with patch.dict("os.environ", {"API_SECRET_KEY": "test"}), patch.object(save, "salva_offerta", return_value={"errore": "Airtable non disponibile"}):
            with self.assertRaises(pipeline.HTTPException) as error:
                save.salva(offer, "test")
            self.assertEqual(error.exception.status_code, 500)

    def test_empty_ocr_does_not_call_ai(self):
        file = types.SimpleNamespace(filename="empty.pdf", file=io.BytesIO(b"pdf"))
        with patch.object(pipeline, "convert_from_path", return_value=[Mock()]), patch.object(pipeline.pytesseract, "image_to_string", return_value="   "), patch.object(pipeline, "estrai_dati_offerta_cte") as extract:
            with self.assertRaises(pipeline.HTTPException) as error:
                pipeline.processa_cte(file)
            self.assertEqual(error.exception.status_code, 422)
            extract.assert_not_called()

    def test_uploads_limit_concurrency_without_blocking_event_loop(self):
        import time
        import threading
        bill = types.ModuleType("estrai_dati_bolletta")
        bill.estrai_dati_bolletta = Mock()
        comparison = types.ModuleType("confronto")
        comparison.confronta_offerte = Mock()
        with patch.dict(sys.modules, {"estrai_dati_bolletta": bill, "confronto": comparison}):
            upload = importlib.import_module("upload_pdf")
        active = 0
        peak = 0
        guard = threading.Lock()
        def process(file):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with guard:
                active -= 1
            return {"nome_offerta": "Test"}
        async def exercise():
            files = [types.SimpleNamespace(filename=f"{i}.PDF") for i in range(5)]
            with patch.object(upload, "cte_slots", asyncio.Semaphore(2)), patch.object(upload, "processa_cte", side_effect=process), patch.dict("os.environ", {"API_SECRET_KEY": "test"}):
                tasks = [asyncio.create_task(upload.upload_cte_pdf(file, "test")) for file in files]
                await asyncio.sleep(0.005)
                self.assertFalse(all(task.done() for task in tasks))
                return await asyncio.gather(*tasks)
        self.assertEqual(len(asyncio.run(exercise())), 5)
        self.assertEqual(peak, 2)

    def test_single_upload_response_unchanged(self):
        bill = types.ModuleType("estrai_dati_bolletta")
        bill.estrai_dati_bolletta = Mock()
        comparison = types.ModuleType("confronto")
        comparison.confronta_offerte = Mock()
        with patch.dict(sys.modules, {"estrai_dati_bolletta": bill, "confronto": comparison}):
            upload = importlib.import_module("upload_pdf")
        file = types.SimpleNamespace(filename="single.pdf", file=io.BytesIO(b"pdf"))
        with patch.object(upload, "processa_cte", return_value={"nome_offerta": "Test"}), patch.dict("os.environ", {"API_SECRET_KEY": "test"}):
            result = asyncio.run(upload.upload_cte_pdf(file, "test"))
        self.assertEqual(result, {"filename": "single.pdf", "output_ai": {"nome_offerta": "Test"}})

    def test_success_and_cleanup(self):
        seen = []
        image = Mock()
        def convert(path):
            seen.append(path)
            self.assertTrue(Path(path).exists())
            return [image]
        file = types.SimpleNamespace(filename="test.pdf", file=io.BytesIO(b"pdf"))
        with patch.object(pipeline, "convert_from_path", side_effect=convert), patch.object(pipeline.pytesseract, "image_to_string", return_value="CTE"):
            self.assertEqual(pipeline.processa_cte(file), {"nome_offerta": "Test"})
        image.close.assert_called_once()
        self.assertFalse(Path(seen[0]).parent.exists())
        ai.estrai_dati_offerta_cte.assert_called_with("\n--- Pagina 1 ---\nCTE")

    def test_corrupt_pdf_cleanup(self):
        seen = []
        def convert(path):
            seen.append(path)
            raise ValueError("PDF corrotto")
        file = types.SimpleNamespace(filename="bad.pdf", file=io.BytesIO(b"bad"))
        with patch.object(pipeline, "convert_from_path", side_effect=convert):
            with self.assertRaises(ValueError):
                pipeline.processa_cte(file)
        self.assertFalse(Path(seen[0]).parent.exists())

    def test_ocr_failure_closes_images(self):
        images = [Mock(), Mock()]
        file = types.SimpleNamespace(filename="test.pdf", file=io.BytesIO(b"pdf"))
        with patch.object(pipeline, "convert_from_path", return_value=images), patch.object(pipeline.pytesseract, "image_to_string", side_effect=RuntimeError("OCR")):
            with self.assertRaises(RuntimeError):
                pipeline.processa_cte(file)
        for image in images:
            image.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

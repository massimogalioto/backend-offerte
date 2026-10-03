import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

test("cartella PDF, errori isolati, retry e collegamento backend nella build Netlify", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const calls: string[] = [];
  let failed = false;
  let active = 0, peak = 0;
  await page.route("http://backend.test/**", async route => {
    const request = route.request();
    if (request.method() === "OPTIONS") { await route.fulfill({ status: 204, headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*" } }); return; }
    expect(request.headers()["x-api-key"]).toBe("browser-test-key");
    let body;
    let status = 200;
    if (request.url().endsWith("upload-cte")) {
      active++; peak = Math.max(peak, active);
      const filename = /filename="([^"]+)"/.exec(request.postDataBuffer()!.toString())![1];
      calls.push(`upload:${filename}`);
      await new Promise(resolve => setTimeout(resolve, 50));
      body = { output_ai: { fornitore: "Test", nome_offerta: filename, tipologia_cliente: "Residenziale", tariffa: "Fisso", tipo_fornitura: "Luce" } };
    } else {
      active = Math.max(0, active - 1);
      const offer = request.postDataJSON();
      calls.push(`save:${offer.fonte_cte}`);
      if (offer.fonte_cte === "b.pdf" && !failed) { failed = true; status = 500; body = { detail: "Airtable temporaneamente non disponibile" }; }
      else body = { successo: true, id: `rec-${offer.fonte_cte}` };
    }
    await route.fulfill({ status, json: body, headers: { "Access-Control-Allow-Origin": "*" } });
  });
  await page.goto("/cte/");
  await page.getByLabel("URL backend HTTPS").fill("http://backend.test");
  await page.getByLabel("Chiave API del backend").fill("browser-test-key");
  await page.getByRole("button", { name: "Salva collegamento" }).click();
  await page.getByRole("tab", { name: "Caricamento massivo" }).click();
  const directory = info.outputPath("documents");
  mkdirSync(directory, { recursive: true });
  for (const name of ["a.pdf", "b.pdf", "c.PDF", "ignored.txt"]) writeFileSync(join(directory, name), "test file");
  await page.locator('input[webkitdirectory]').setInputFiles(directory);
  await expect(page.getByText("CTE trovate:")).toContainText("3");
  await page.getByRole("button", { name: "ELABORA TUTTE LE CTE" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Totale: 3" })).toContainText("Completate: 2 — Errori: 1");
  expect(peak).toBe(2);
  const before = calls.length;
  await page.getByRole("button", { name: "Riprova errori" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Totale: 3" })).toContainText("Completate: 3 — Errori: 0");
  expect(calls.slice(before)).toEqual(["save:b.pdf"]);
  expect(errors).toEqual([]);
  await page.goto("/bollette/");
  await expect(page.getByRole("heading", { name: "Carica la bolletta", exact: true })).toBeVisible();
  await page.goto("/");
  await expect(page.locator("main")).toBeVisible();
});

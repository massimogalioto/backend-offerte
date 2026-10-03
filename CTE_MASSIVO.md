# Caricamento massivo CTE

## Ripresa dopo lo spegnimento

All'avvio `git status --short` mostrava modifiche a `upload_pdf.py` e
`salva_offerta_endpoint.py`, oltre a `.gitignore`, questo documento,
`cte_pipeline.py`, `frontend/` e `tests/` non ancora tracciati.
Sono stati esaminati il diff completo e tutti i sorgenti non committati.
La pipeline OCR condivisa, la coda browser e il frontend Next.js erano già
implementati: sono stati mantenuti e completati, senza reset o ripristini.

## Funzionamento

Nella pagina CTE scegli **Caricamento massivo**, seleziona la cartella e premi
**Elabora tutte le CTE**. Vengono elencati solo PDF, anche con estensione maiuscola,
compresi quelli nelle sottocartelle. Ogni PDF deve avere dimensione tra 1 byte e
25 MB; i file non validi ricevono un errore senza bloccare gli altri.

Due worker eseguono ciascuno upload, OCR, `estrai_dati_offerta_cte()` e salvataggio
tramite `/salva-offerta` e la funzione Airtable già esistente. `fonte_cte` viene
impostata al nome originale del file, senza il percorso della cartella.
Gli stati sono IN ATTESA, ELABORAZIONE, SALVATAGGIO, COMPLETATA, ERRORE.
La barra misura i file terminati, con conteggi distinti di completati ed errori.
**Riprova errori** ritenta solo i file falliti; se l'estrazione era riuscita,
ritenta solo il salvataggio Airtable.

`MAX_CONCURRENT = 2` in `frontend/cte-batch.ts` limita l'intero ciclo di ogni file.
Il backend limita anche gli upload CTE a due per processo e sposta OCR/AI nel
thread pool, mantenendo libero l'event loop. Con più repliche il limite backend
non è globale. I temporanei CTE e le immagini vengono chiusi anche dopo errori.
L'OCR senza testo produce HTTP 422, senza chiamare l'AI.

Gli endpoint esistenti e i loro payload sono mantenuti. Il frontend conserva
anche CTE singola con salvataggio manuale e analisi/confronto bollette.
Nessun PostgreSQL o nuovo schema Airtable.

## Cartella pronta per Netlify

La cartella da trascinare su Netlify è **`frontend/netlify-upload/`**: contiene
`index.html`, `cte/index.html`, `bollette/index.html`, asset e intestazioni HTTP.
Non caricare i sorgenti frontend o `.next` con il caricamento manuale.

Il sito statico chiama direttamente il backend HTTPS. Alla prima apertura,
nel pannello **Collegamento al servizio**, inserisci:

1. L'URL pubblico del backend FastAPI, senza il percorso di un endpoint.
2. La chiave corrispondente a `API_SECRET_KEY` del backend, se configurata.
3. Premi **Salva collegamento**.

La chiave è salvata solo in `sessionStorage` della scheda corrente, inviata con
`x-api-key` e mai incorporata nella build o pubblicata su GitHub. La pagina
statica è pubblica; l'autorizzazione delle operazioni avviene sul backend.
Le credenziali OpenAI e Airtable rimangono esclusivamente sul backend.
La selezione dei PDF non invia dati finché non avvii l'elaborazione.

L'URL reale del backend non è presente nel repository e non è stato fornito
alla ripresa: la cartella richiede questa configurazione iniziale. Non è stato
eseguito un salvataggio reale in Airtable o un deploy sul tuo account Netlify.
Il backend deve essere raggiungibile, avere le variabili già previste dal
progetto, Tesseract italiano e Poppler (installati dal Dockerfile). Il CORS
attuale permette le richieste dal sito Netlify, inclusa l'intestazione x-api-key.
Eventuali restrizioni CORS future devono includere il dominio effettivo Netlify.

## Deploy automatico dopo push GitHub

`netlify.toml` alla radice configura:

- directory base: `frontend`;
- comando: `npm run build:static`;
- directory pubblicata: `netlify-upload`;
- Node 22, senza runtime/adattatore Next.js per la build statica.

Collega una volta il sito Netlify al repository GitHub e abilita il deploy del
branch desiderato. Per preconfigurare l'URL, imposta su Netlify la variabile
pubblica `NEXT_PUBLIC_BACKEND_URL=https://URL-REALE-DEL-BACKEND` e ricostruisci.
Non mettere chiavi in variabili `NEXT_PUBLIC_*`.
Il push aggiorna il frontend solo per un sito collegato al repository: un
caricamento manuale da solo non crea il collegamento GitHub. Il servizio backend
va a sua volta collegato al repository presso il provider che lo ospita, se vuoi
aggiornarlo automaticamente al push. Netlify ospita questa build frontend,
non il processo FastAPI/OCR.

Per rigenerare localmente: `cd frontend`, `npm ci`, `npm run build:static`.
Lo script copia i sorgenti in `.static-build/`, esclude solo il proxy API dalla
copia e genera l'export senza spostare o modificare gli originali. Rimuove e
rigenera esclusivamente le due cartelle generate a percorso fisso
`.static-build/` e `netlify-upload/`, escluse da Git. Il lockfile è incluso.
La `.dockerignore` evita di includere frontend, dipendenze e strumenti locali
nell'immagine del backend.

## Modalità Next.js con server

Resta disponibile `npm run build` / `npm start`, con il proxy `/api/service`.
Configura `BACKEND_URL`, `API_SECRET_KEY`, `FRONTEND_USERNAME` e
`FRONTEND_PASSWORD` lato server come in `frontend/.env.example`.
Il proxy controlla origine, endpoint ammessi e PDF; aggiunge la chiave lato server.
L'accesso HTTP Basic è obbligatorio in produzione in questa modalità.
La cartella Netlify statica non usa il proxy né HTTP Basic del server Next.js.

## Verifiche eseguite

- Backend: `python -m unittest discover -s tests -v`: 8 test superati.
- Frontend: `npm test`: 9 test superati.
- TypeScript: `npm run typecheck`: superato.
- Build Next.js con proxy: `npm run build -- --webpack`: superata.
- Build Netlify: `npm run build:static`: superata; cartella generata.
- Browser Chromium: `npm run test:e2e`: superato sulla build statica.
  Verifica configurazione URL/chiave, selezione di tre PDF e un TXT ignorato,
  concorrenza 2, errore Airtable isolato, retry solo salvataggio del file fallito,
  fonte CTE, assenza di errori JavaScript, percorsi homepage e bollette.
- I test OCR, AI e Airtable usano mock e non creano record reali.

Node è disponibile in `.tools/node-v22.23.3-win-x64`; l'ambiente Python di test è
`.tools/venv`. Questi strumenti sono locali e ignorati da Git. Per i test browser
installa Chromium con `npx playwright install chromium`; se usi la cartella locale
imposta `PLAYWRIGHT_BROWSERS_PATH` al percorso assoluto `.tools/browsers`.

## Limiti e aspetti preesistenti

La coda è asincrona nel browser, non persistente: mantieni la scheda aperta.
Stati e risultati si perdono al ricaricamento o alla selezione di un'altra
cartella. Il timeout per richiesta è 300 secondi. Dopo un timeout di salvataggio,
il record potrebbe già esistere: verifica Airtable prima del retry per evitare
duplicati. Non sono previsti retry automatici.

L'AI può restituire un oggetto `errore` con HTTP 200: il frontend lo tratta come
fallimento e non lo salva. La verifica API key di salva-offerta differisce da
quella degli upload quando la chiave non è configurata: in modalità statica lascia
il campo chiave vuoto in quel caso. I temporanei degli altri endpoint e i duplicati
OpenAI/PyPDF2 in requirements.txt sono aspetti preesistenti non cambiati qui.

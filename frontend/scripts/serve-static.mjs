import { createServer } from "node:http";
import { readFileSync, statSync } from "node:fs";
import { resolve, extname, sep } from "node:path";
const root = resolve("netlify-upload");
const types = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".txt": "text/plain" };
createServer((request, response) => {
  try {
    let path = resolve(root, "." + decodeURIComponent(new URL(request.url, "http://localhost").pathname));
    if (path !== root && !path.startsWith(root + sep)) throw new Error("Invalid path");
    if (statSync(path).isDirectory()) path = resolve(path, "index.html");
    response.setHeader("Content-Type", types[extname(path)] ?? "application/octet-stream");
    response.end(readFileSync(path));
  } catch { response.writeHead(404); response.end("Not found"); }
}).listen(4173, "127.0.0.1");

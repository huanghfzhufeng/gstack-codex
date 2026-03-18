import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const port = Number(process.env.PORT || 4300);

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
  const relative = url.pathname === "/" ? "public/index.html" : url.pathname.slice(1);
  const filePath = path.join(__dirname, relative);

  if (!filePath.startsWith(__dirname)) {
    res.writeHead(403, { "content-type": "text/plain; charset=utf-8" });
    res.end("Forbidden");
    return;
  }

  try {
    const contents = await fs.readFile(filePath);
    res.writeHead(200, { "content-type": mimeTypes[path.extname(filePath)] || "text/plain; charset=utf-8" });
    res.end(contents);
  } catch {
    res.writeHead(404, { "content-type": "text/html; charset=utf-8" });
    res.end("<h1>404</h1><p>Missing fixture asset.</p>");
  }
});

server.listen(port, () => {
  console.log(`QA fixture running at http://127.0.0.1:${port}`);
});

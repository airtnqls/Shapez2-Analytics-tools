import { createServer } from "node:http";
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const root = fileURLToPath(new URL("../out/", import.meta.url));
const portArg = process.argv.find((arg) => /^\d+$/.test(arg));
const port = Number(process.env.PORT || portArg || 4173);
const shouldOpen = process.argv.includes("--open");
const host = "127.0.0.1";
const appUrl = `http://${host}:${port}`;

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".webmanifest": "application/manifest+json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gz": "application/gzip",
  ".txt": "text/plain; charset=utf-8",
  ".wasm": "application/wasm",
};

function openBrowser(url) {
  const platform = process.platform;
  const command = platform === "win32" ? "cmd" : platform === "darwin" ? "open" : "xdg-open";
  const args = platform === "win32" ? ["/c", "start", "", url] : [url];
  const child = spawn(command, args, { detached: true, stdio: "ignore", windowsHide: true });
  child.on("error", () => {
    console.log(`Open this address manually: ${url}`);
  });
  child.unref();
}

function resolveRequestPath(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }

  // URL paths always use '/'. Remove every leading slash before joining so a
  // request can never replace the Windows drive/root of the static directory.
  const stripped = decoded.replace(/^[/\\]+/, "");
  const normalized = normalize(stripped || "index.html");
  const candidate = join(root, normalized);
  const rel = relative(root, candidate);
  if (rel.startsWith(`..${sep}`) || rel === ".." || rel.includes(`..${sep}`) || rel === "") {
    return rel === "" ? join(root, "index.html") : null;
  }
  return candidate;
}

const server = createServer((request, response) => {
  const url = new URL(request.url || "/", appUrl);
  let file = resolveRequestPath(url.pathname);
  if (file && url.pathname.endsWith("/") && !file.endsWith("index.html")) {
    file = join(file, "index.html");
  }
  if (!file || !existsSync(file) || statSync(file).isDirectory()) {
    file = join(root, "404.html");
    response.statusCode = 404;
  }

  response.setHeader("Cross-Origin-Opener-Policy", "same-origin");
  response.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader(
    "Cache-Control",
    url.pathname === "/sw.js"
      ? "no-cache, no-store, must-revalidate"
      : url.pathname.startsWith("/_next/static/")
        ? "public, max-age=31536000, immutable"
        : url.pathname.startsWith("/data/") || url.pathname === "/solver.worker.js"
          ? "no-cache, must-revalidate"
          : "no-cache",
  );
  response.setHeader("Content-Type", types[extname(file).toLowerCase()] || "application/octet-stream");

  const stream = createReadStream(file);
  stream.on("error", (error) => {
    console.error(error);
    if (!response.headersSent) response.statusCode = 500;
    response.end("Static file read failed.");
  });
  stream.pipe(response);
});

server.on("error", (error) => {
  if (error && error.code === "EADDRINUSE") {
    console.error(`Port ${port} is already in use.`);
    console.error(`Close the previous server or open ${appUrl} in your browser.`);
  } else {
    console.error(error);
  }
  process.exitCode = 1;
});

server.listen(port, host, () => {
  console.log(`Shapez2 TMAM Studio 2.1.0: ${appUrl}`);
  console.log(`Static root: ${root}`);
  console.log("Press Ctrl+C to stop.");
  if (shouldOpen) setTimeout(() => openBrowser(appUrl), 250);
});

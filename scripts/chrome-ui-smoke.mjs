import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const chrome = process.env.CHROME_PATH
  ?? "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 10_000 + (process.pid % 40_000);
const webPort = 20_000 + (process.pid % 20_000);
const baseUrl = `http://127.0.0.1:${webPort}`;
const profile = await mkdtemp(path.join(os.tmpdir(), "shapez2-chrome-"));
const reportDir = path.resolve("reports/dev-verification");
await mkdir(reportDir, { recursive: true });

const browser = spawn(chrome, [
  "--headless=new",
  "--disable-gpu",
  "--disable-breakpad",
  "--disable-crash-reporter",
  "--disable-dev-shm-usage",
  "--hide-scrollbars",
  "--no-first-run",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`,
  "--window-size=1440,900",
  "about:blank",
], { stdio: "ignore", windowsHide: true });
const webServer = spawn("python", ["-m", "backend.server", "--port", String(webPort), "--no-open"], {
  cwd: process.cwd(), stdio: "ignore", windowsHide: true,
});

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function json(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

let socket;
let shutdownBrowser;
try {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/health`);
      if (response.ok) break;
    } catch {}
    if (attempt === 79) throw new Error("local Python web backend did not start");
    await sleep(100);
  }
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      await json(`http://127.0.0.1:${port}/json/version`);
      break;
    } catch {
      if (attempt === 49) throw new Error("Chrome DevTools did not start");
      await sleep(100);
    }
  }
  const page = await json(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent(baseUrl)}`,
    { method: "PUT" },
  );
  socket = new WebSocket(page.webSocketDebuggerUrl);
  socket.binaryType = "arraybuffer";
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });

  let nextId = 0;
  const pending = new Map();
  const errors = [];
  socket.addEventListener("message", (event) => {
    const payload = typeof event.data === "string" ? event.data : Buffer.from(event.data).toString("utf8");
    const message = JSON.parse(payload);
    if (message.id && pending.has(message.id)) {
      const waiter = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) waiter.reject(new Error(`${waiter.method}: ${message.error.message}`));
      else waiter.resolve(message.result);
    }
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error") errors.push(message.params.entry.text);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    nextId += 1;
    pending.set(nextId, { resolve, reject, method });
    socket.send(JSON.stringify({ id: nextId, method, params }));
  });
  shutdownBrowser = () => send("Browser.close");
  const evaluate = async (expression) => {
    const response = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    return response.result.value;
  };

  await Promise.all([send("Page.enable"), send("Runtime.enable"), send("Log.enable")]);
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (await evaluate("document.readyState === 'complete' && document.body.innerText.includes('Shapez2Analyzer Web') && document.body.innerText.includes('건물 작동')")) break;
    if (attempt === 79) throw new Error("initial UI did not become ready");
    await sleep(100);
  }
  const initialOverlay = await evaluate("Boolean(document.querySelector('[data-nextjs-dialog], .vite-error-overlay'))");
  const capTarget = "--PP:--PP:--Pc:SSSS:-SS-:cS-S";
  const targetEntered = await evaluate(`(() => {
    const input = document.querySelector('.legacy-left-panel input.font-mono');
    if (!input) return false;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, ${JSON.stringify("--PP:--PP:--Pc:SSSS:-SS-:cS-S")});
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  })()`);
  if (!targetEntered) throw new Error("input A was not found");
  const analysisClicked = await evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find((item) => item.textContent.trim() === '상세 분석');
    if (!button) return false;
    button.click();
    return true;
  })()`);
  if (!analysisClicked) throw new Error("상세 분석 button was not found");
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const ready = await evaluate("document.body.innerText.includes('분석 C7') && document.body.innerText.includes('pp-receipt-chain')");
    if (ready) break;
    if (attempt === 299) throw new Error(`adaptive cap analysis did not resolve ${capTarget} at C7`);
    await sleep(100);
  }
  const clicked = await evaluate(`(() => {
    const button = [...document.querySelectorAll('.legacy-main-tabs button')].find((item) => item.textContent.trim() === '공정 트리');
    if (!button) return false;
    button.click();
    return true;
  })()`);
  if (!clicked) throw new Error("공정 트리 tab was not found");

  for (let attempt = 0; attempt < 400; attempt += 1) {
    const ready = await evaluate("Boolean(document.querySelector('.react-flow')) && document.body.innerText.includes('재생 검증') && document.querySelectorAll('.react-flow__node-operation').length > 0");
    if (ready) break;
    if (attempt === 399) {
      const failureState = await evaluate(`({ text: document.body.innerText.slice(-2200), html: document.body.innerHTML.slice(-1000), overlay: Boolean(document.querySelector('[data-nextjs-dialog], .vite-error-overlay')) })`);
      const failureShot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
      await writeFile(path.join(reportDir, "web-process-graph-error.png"), Buffer.from(failureShot.data, "base64"));
      throw new Error(`process graph did not render: ${JSON.stringify({ failureState, errors })}`);
    }
    await sleep(100);
  }
  await evaluate("document.querySelectorAll('[data-proof-operation]')[document.querySelectorAll('[data-proof-operation]').length - 2]?.click()");
  await sleep(350);
  const overlay = await evaluate("Boolean(document.querySelector('[data-nextjs-dialog], .vite-error-overlay'))");
  const localSummary = await evaluate(`({
    hasContent: document.body.innerText.trim().length > 100,
    hasGraph: Boolean(document.querySelector('.react-flow')),
    nodeCount: document.querySelectorAll('.react-flow__node').length,
    operationCount: document.querySelectorAll('.react-flow__node-operation').length,
    edgeCount: document.querySelectorAll('.react-flow__edge').length,
    hasArrowMarker: Boolean(document.querySelector('.react-flow marker')),
    scope: document.querySelector('.legacy-process-view')?.dataset.scope,
    direction: document.querySelector('.legacy-process-view')?.dataset.direction,
    operationListCount: document.querySelectorAll('[data-proof-operation]').length,
    text: document.body.innerText.slice(0, 800),
  })`);
  const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  const screenshotPath = path.join(reportDir, "web-process-graph.png");
  await writeFile(screenshotPath, Buffer.from(screenshot.data, "base64"));
  const fullNodeCount = localSummary.operationListCount;
  const tallHalfTarget = "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----";
  await evaluate(`[...document.querySelectorAll('.legacy-main-tabs button')].find((item) => item.textContent.trim() === '분석 도구')?.click()`);
  await evaluate(`(() => {
    const input = document.querySelector('.legacy-left-panel input.font-mono');
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, ${JSON.stringify("SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----")});
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
  await evaluate(`[...document.querySelectorAll('button')].find((item) => item.textContent.trim() === '상세 분석')?.click()`);
  for (let attempt = 0; attempt < 300; attempt += 1) {
    if (await evaluate("document.body.innerText.includes('분석 C11') && document.body.innerText.includes('POSSIBLE / HALF / half')")) break;
    if (attempt === 299) throw new Error("11-layer HALF did not resolve as POSSIBLE");
    await sleep(100);
  }
  await evaluate(`[...document.querySelectorAll('.legacy-main-tabs button')].find((item) => item.textContent.trim() === '공정 트리')?.click()`);
  for (let attempt = 0; attempt < 400; attempt += 1) {
    if (await evaluate("Boolean(document.querySelector('.react-flow')) && document.querySelectorAll('[data-proof-operation]').length > 270")) break;
    if (attempt === 399) throw new Error("11-layer HALF full DAG did not render");
    await sleep(100);
  }
  await evaluate("document.querySelectorAll('[data-proof-operation]')[document.querySelectorAll('[data-proof-operation]').length - 1]?.click()");
  await sleep(350);
  const tallHalfLocalNodeCount = await evaluate("document.querySelectorAll('.react-flow__node').length");
  const tallHalfFullNodeCount = await evaluate("document.querySelectorAll('[data-proof-operation]').length");
  const tallHalfMaxVisibleLayers = await evaluate("Math.max(0, ...[...document.querySelectorAll('.proof-node-shape')].map((node) => Number(node.dataset.layerCount || 0)))");
  const tallHalfShot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  const tallHalfScreenshotPath = path.join(reportDir, "web-tall-half-process-graph.png");
  await writeFile(tallHalfScreenshotPath, Buffer.from(tallHalfShot.data, "base64"));
  if (initialOverlay || overlay || !localSummary.hasContent || !localSummary.hasGraph || localSummary.nodeCount < 2 || localSummary.operationCount < 1 || localSummary.edgeCount < 1 || !localSummary.hasArrowMarker || localSummary.scope !== "full" || localSummary.direction !== "LR" || fullNodeCount < 235 || tallHalfLocalNodeCount < 2 || tallHalfFullNodeCount < 271 || tallHalfMaxVisibleLayers !== 11 || errors.length) {
    throw new Error(JSON.stringify({ initialOverlay, overlay, errors, localSummary, fullNodeCount, tallHalfLocalNodeCount, tallHalfFullNodeCount, tallHalfMaxVisibleLayers }));
  }
  console.log(JSON.stringify({ status: "PASS", initialOverlay, overlay, errors, adaptiveCap: { target: capTarget, effective: 7, verdict: "POSSIBLE", route: "pp-receipt-chain" }, pinPushDag: { localNodeCount: localSummary.nodeCount, localOperationCount: localSummary.operationCount, fullNodeCount, screenshotPath }, tallHalf: { target: tallHalfTarget, effective: 11, verdict: "POSSIBLE", route: "half", localNodeCount: tallHalfLocalNodeCount, fullNodeCount: tallHalfFullNodeCount, screenshotPath: tallHalfScreenshotPath } }, null, 2));
} finally {
  try { await shutdownBrowser?.(); } catch {}
  await sleep(250);
  socket?.close();
  browser.kill();
  try { await fetch(`${baseUrl}/api/shutdown`, { method: "POST" }); } catch {}
  await sleep(250);
  if (webServer.exitCode == null) webServer.kill();
  await sleep(250);
  try { await rm(profile, { recursive: true, force: true }); } catch {}
}

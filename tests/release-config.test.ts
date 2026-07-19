import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("release cache and client-only contracts", () => {
  it("revalidates stable solver and data URLs", () => {
    const config = JSON.parse(readFileSync("vercel.json", "utf8")) as { headers: Array<{ source: string; headers: Array<{ key: string; value: string }> }> };
    for (const source of ["/data/(.*)", "/solver.worker.js"]) {
      const rule = config.headers.find((item) => item.source === source);
      expect(rule?.headers.find((header) => header.key === "Cache-Control")?.value).toBe("no-cache, must-revalidate");
    }
  });

  it("uses network-first service-worker handling for mutable solver assets", () => {
    const source = readFileSync("public/sw.js", "utf8");
    expect(source).toContain('url.pathname === "/solver.worker.js" || url.pathname.startsWith("/data/")');
    expect(source).toContain('fetch(event.request, { cache: "no-store" })');
  });

  it("does not expose server-side analyze or operate endpoints", () => {
    const source = readFileSync("backend/server.py", "utf8");
    expect(source).not.toContain('path == "/api/analyze"');
    expect(source).not.toContain('path == "/api/operate"');
  });
});

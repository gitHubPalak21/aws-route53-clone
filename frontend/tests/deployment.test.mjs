import assert from "node:assert/strict";
import test from "node:test";
import { loadTypeScript } from "./load-typescript.mjs";

test("production defaults to same-origin API requests without localhost", (t) => {
  t.mock.property(process, "env", { ...process.env, NODE_ENV: "production", NEXT_PUBLIC_API_BASE_URL: undefined });
  assert.equal(loadTypeScript("lib/config.ts").config.apiBaseUrl, "");
});

test("explicit same-origin and development API configurations remain supported", (t) => {
  t.mock.property(process, "env", { ...process.env, NODE_ENV: "development", NEXT_PUBLIC_API_BASE_URL: "" });
  assert.equal(loadTypeScript("lib/config.ts").config.apiBaseUrl, "");
  process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.test/";
  assert.equal(loadTypeScript("lib/config.ts").config.apiBaseUrl, "https://api.example.test");
  for (const url of ["ftp://api.example.test", "https://user:secret@api.example.test", "https://api.example.test?token=secret"]) {
    process.env.NEXT_PUBLIC_API_BASE_URL = url;
    assert.throws(() => loadTypeScript("lib/config.ts"), /HTTP\(S\) base URL/);
  }
});

test("server rewrite preserves API paths and rejects unsafe proxy destinations", async (t) => {
  t.mock.property(process, "env", { ...process.env, API_PROXY_TARGET: "https://api.example.test/" });
  assert.deepEqual(await loadTypeScript("next.config.ts").default.rewrites(), [
    { source: "/api/:path*", destination: "https://api.example.test/api/:path*" },
  ]);
  for (const url of ["ftp://api.example.test", "https://user:secret@api.example.test", "https://api.example.test/private", "https://api.example.test?key=secret"]) {
    process.env.API_PROXY_TARGET = url;
    assert.throws(() => loadTypeScript("next.config.ts"), /HTTP\(S\) origin/);
  }
});

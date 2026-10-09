import assert from "node:assert/strict";
import test from "node:test";
import { loadTypeScript } from "./load-typescript.mjs";

const cache = new Map();
const { ApiError, apiRequest } = loadTypeScript("lib/api/client.ts", cache);
const { validationFeedback } = loadTypeScript("lib/api/validation-errors.ts", cache);
const { validateZoneForm, zonePayload } = loadTypeScript("lib/hosted-zones/form-values.ts", cache);
const { safeReturnTo } = loadTypeScript("lib/auth/redirects.ts", cache);

test("FastAPI errors map nested value locations and ignore malformed feedback", () => {
  const feedback = validationFeedback(new ApiError("Invalid request", 422, { detail: [
    { loc: ["body", "name"], msg: "Value error, Invalid domain", input: "not rendered" },
    { loc: ["body", "values", 0], msg: "Invalid IPv4 address" },
    { loc: ["body"], msg: "Private zones require VPC metadata" },
    null, { msg: 1 }, "invalid",
  ] }));
  assert.deepEqual(feedback.fields, { name: "Invalid domain", values: "Invalid IPv4 address" });
  assert.deepEqual(feedback.messages, ["Invalid domain", "Invalid IPv4 address", "Private zones require VPC metadata"]);
  for (const details of [null, "bad", {}, { detail: "Invalid request" }]) {
    assert.deepEqual(validationFeedback(new ApiError("Invalid request", 422, details)), { fields: {}, messages: [] });
  }
});

test("API helper includes cookies and JSON headers and accepts 204", async (t) => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.ok(url.endsWith("/api/example"));
    assert.equal(options.credentials, "include");
    assert.equal(options.headers.get("Content-Type"), "application/json");
    assert.equal(options.headers.get("Accept"), "application/json");
    assert.equal(options.body, '{"name":"example.com"}');
    return new Response(null, { status: 204 });
  });
  assert.equal(await apiRequest("/api/example", { method: "PATCH", json: { name: "example.com" } }), undefined);
});

test("API failures preserve validation details without leaking non-JSON server bodies", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ detail: "Record already exists" }), { status: 409 }));
  await assert.rejects(apiRequest("/api/example"), (error) => error instanceof ApiError && error.status === 409 && error.message === "Record already exists");
  globalThis.fetch = async () => new Response("Internal traceback", { status: 500 });
  await assert.rejects(apiRequest("/api/example"), (error) => error.message === "API request failed (500).");
  globalThis.fetch = async () => new Response("invalid JSON", { status: 200 });
  await assert.rejects(apiRequest("/api/example"), (error) => error.message === "The API returned invalid JSON.");
});

test("API cancellations stay distinguishable from connection failures", async (t) => {
  const aborted = new DOMException("Aborted", "AbortError");
  t.mock.method(globalThis, "fetch", async () => { throw aborted; });
  await assert.rejects(apiRequest("/api/example"), (error) => error === aborted);
  globalThis.fetch = async () => { throw new TypeError("Connection failed"); };
  await assert.rejects(apiRequest("/api/example"), (error) => error instanceof ApiError && error.status === null);
  await assert.rejects(apiRequest("//outside.example"), /single slash/);
});

test("private metadata is required and public payloads discard hidden stale fields", () => {
  const values = { name: " Example.COM. ", comment: " Production ", zone_type: "PRIVATE", region: "", vpc_id: "" };
  const errors = validateZoneForm(values);
  assert.ok(errors.region);
  assert.ok(errors.vpc_id);
  assert.deepEqual(validateZoneForm({ ...values, region: "ap-south-1", vpc_id: "vpc-0123456789abcdef" }), {});
  assert.deepEqual(zonePayload({ ...values, zone_type: "PUBLIC", region: "ap-south-1", vpc_id: "vpc-0123456789abcdef" }), {
    name: "example.com", comment: "Production", zone_type: "PUBLIC", region: null, vpc_id: null,
  });
  for (const name of ["", "bad domain.com", "https://example.com", "a".repeat(64) + ".com"]) {
    assert.ok(validateZoneForm({ ...values, zone_type: "PUBLIC", name }).name);
  }
});

test("auth return paths reject external, encoded and query-bearing destinations", () => {
  assert.equal(safeReturnTo("/route53/hosted-zones"), "/route53/hosted-zones");
  for (const path of ["https://evil.example", "//evil.example", "/%2f%2fevil.example", "/route53?next=evil", null]) {
    assert.equal(safeReturnTo(path), "/route53");
  }
});

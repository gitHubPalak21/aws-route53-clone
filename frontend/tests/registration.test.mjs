import assert from "node:assert/strict";
import test from "node:test";
import { loadTypeScript } from "./load-typescript.mjs";

const cache = new Map();
const { validateSignup, registrationPayload, registrationError } = loadTypeScript("lib/auth/registration.ts", cache);
const { ApiError } = loadTypeScript("lib/api/client.ts", cache);
const { register } = loadTypeScript("lib/api/auth.ts", cache);
const valid = { display_name: " Palak ", email: " USER@Example.com ", password: "password123", confirm_password: "password123" };

test("signup validates required fields and matching passwords", () => {
  assert.deepEqual(validateSignup(valid), {});
  assert.deepEqual(Object.keys(validateSignup({ display_name: " ", email: "", password: "", confirm_password: "" })),
    ["display_name", "email", "password", "confirm_password"]);
  for (const email of ["bad", "bad domain@example.com", "a@@example.com"]) assert.ok(validateSignup({ ...valid, email }).email);
  assert.ok(validateSignup({ ...valid, password: "short" }).password);
  assert.ok(validateSignup({ ...valid, confirm_password: "different" }).confirm_password);
  assert.ok(validateSignup({ ...valid, display_name: "x".repeat(129) }).display_name);
  assert.ok(validateSignup({ ...valid, password: "x".repeat(1025) }).password);
});

test("signup normalizes identity without trimming password or sending confirmation", () => {
  assert.deepEqual(registrationPayload({ ...valid, password: " password123 " }),
    { display_name: "Palak", email: "user@example.com", password: " password123 " });
});

test("registration returns the authenticated user with existing credentialed API", async (t) => {
  const user = { id: 2, email: "user@example.com", display_name: "Palak" };
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.ok(url.endsWith("/api/auth/register"));
    assert.equal(options.method, "POST");
    assert.equal(options.credentials, "include");
    assert.deepEqual(JSON.parse(options.body), registrationPayload(valid));
    return Response.json({ user }, { status: 201 });
  });
  assert.deepEqual(await register(registrationPayload(valid)), user);
});

test("signup duplicate and backend validation feedback is useful and sanitized", () => {
  const duplicate = registrationError(new ApiError("duplicate", 409));
  assert.equal(duplicate.fields.email, "An account with this email already exists.");
  const invalid = registrationError(new ApiError("invalid", 422, { detail: [
    { loc: ["body", "password"], msg: "String should have at least 8 characters", input: "secret" },
  ] }));
  assert.equal(invalid.fields.password, "String should have at least 8 characters");
  assert.ok(!JSON.stringify(invalid).includes("secret"));
  for (const status of [400, 500, null]) assert.ok(registrationError(new ApiError("traceback", status)).message);
});

test("registration API failures remain errors and do not create frontend-only identity", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ detail: "An account with this email already exists." }, { status: 409 }));
  await assert.rejects(register(registrationPayload(valid)), (error) => error instanceof ApiError && error.status === 409);
  globalThis.fetch = async () => Response.json({}, { status: 201 });
  await assert.rejects(register(registrationPayload(valid)), (error) => error.status === 502);
});

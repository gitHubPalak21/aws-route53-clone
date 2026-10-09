import assert from "node:assert/strict";
import test from "node:test";
import { loadTypeScript } from "./load-typescript.mjs";

// Test the browser-compatible rules with Node's runner; no additional test dependencies.
const rules = loadTypeScript("lib/validation/dns-records.ts");
const zone = "example.com";

test("relative, apex and absolute names match backend boundaries", () => {
  for (const [input, type, expected] of [
    ["", "A", zone], ["@", "TXT", zone], [" WWW ", "A", "www.example.com"],
    ["www.example.com.", "A", "www.example.com"], ["_sip._tcp", "SRV", "_sip._tcp.example.com"],
    ["_acme-challenge", "TXT", "_acme-challenge.example.com"], ["*", "A", "*.example.com"],
  ]) {
    const result = rules.recordName(input, zone, type);
    assert.equal(result.error, undefined, input);
    assert.equal(result.name, expected);
  }
  for (const [input, type] of [
    ["outside.net", "A"], ["nested.relative", "A"], ["www.", "A"], ["https://example.com", "A"],
    ["bad name", "A"], ["-bad", "A"], ["a".repeat(64), "A"], ["_sip._tcp", "A"], ["*", "SRV"], ["@", "CNAME"],
  ]) assert.ok(rules.recordName(input, zone, type).error, `${input} ${type}`);
});

test("strict IPv4 and standard IPv6 parsing", () => {
  for (const value of ["0.0.0.0", "192.0.2.10", "255.255.255.255"]) assert.equal(rules.recordValueError(value, "A"), undefined);
  for (const value of ["999.1.1.1", "192.168.01.1", "127.1", "hello"]) assert.ok(rules.recordValueError(value, "A"));
  for (const value of ["::", "::1", "2001:db8::1", "1:2:3:4:5:6:7:8", "::ffff:192.0.2.1"]) assert.equal(rules.recordValueError(value, "AAAA"), undefined, value);
  for (const value of ["2001:::1", "1::2::3", "1:2:3", "fe80::1%eth0", "[::1]", "::ffff:192.00.2.1"]) assert.ok(rules.recordValueError(value, "AAAA"), value);
});

test("hostname, TXT, MX, SRV and CAA values respect backend limits", () => {
  for (const type of ["CNAME", "NS", "PTR"]) {
    assert.equal(rules.recordValueError("host.example.net.", type), undefined);
    for (const value of ["https://example.net", "192.0.2.1", "bad..net", "bad name"]) assert.ok(rules.recordValueError(value, type));
  }
  for (const [type, valid, invalid] of [
    ["TXT", 'v=spf1  include:_spf.example.com ~all', '"   "'],
    ["MX", "65535 mail.example.com", "65536 mail.example.com"],
    ["SRV", "0 65535 5060 sip.example.com", "10 5 -1 sip.example.com"],
    ["CAA", '255 issue "letsencrypt.org"', "256 issue letsencrypt.org"],
  ]) {
    assert.equal(rules.recordValueError(valid, type), undefined);
    assert.ok(rules.recordValueError(invalid, type));
  }
  assert.equal(rules.recordValueError("0 0 0 .", "SRV"), undefined);
  for (const value of ["", "   ", "text\nsecond", "a".repeat(4097)]) assert.ok(rules.recordValueError(value, "TXT"));
  assert.ok(rules.recordValueError("mail.example.com", "MX"));
  assert.ok(rules.recordValueError("0 issue! example.com", "CAA"));
});

test("TTL bounds and CNAME cardinality block invalid submissions", () => {
  const values = { name: "www", record_type: "A", values: ["192.0.2.10"], ttl: "300" };
  assert.deepEqual(rules.validateRecordForm(values, zone), {});
  for (const ttl of ["0", "-1", "1.5", "1e3", "2147483648", ""]) assert.ok(rules.validateRecordForm({ ...values, ttl }, zone).ttl, ttl);
  for (const ttl of ["1", "2147483647"]) assert.equal(rules.validateRecordForm({ ...values, ttl }, zone).ttl, undefined);
  assert.ok(rules.validateRecordForm({ ...values, record_type: "CNAME", values: ["a.net", "b.net"] }, zone).values);
  assert.equal(rules.USER_RECORD_TYPES.includes("SOA"), false);
  assert.equal(rules.USER_RECORD_TYPES.length, 9);
});

test("payload preserves internal text spaces and sends only supported fields", () => {
  const payload = rules.recordPayload({ name: " Text ", record_type: "TXT", values: ["  v=spf1  include:example.com ~all  "], ttl: " 600 " }, zone);
  assert.deepEqual(payload, { name: "text.example.com", record_type: "TXT", values: ["v=spf1  include:example.com ~all"], ttl: 600, routing_policy: "SIMPLE" });
});

test("edit initialization keeps nested FQDNs and relativizes service names safely", () => {
  const base = { name: "www.sub.example.com", record_type: "A", values: ["192.0.2.1"], ttl: 600 };
  assert.equal(rules.initialRecordValues(zone, base).name, "www.sub.example.com");
  assert.equal(rules.initialRecordValues(zone, { ...base, name: "_sip._tcp.example.com", record_type: "SRV" }).name, "_sip._tcp");
  assert.equal(rules.initialRecordValues(zone, { ...base, name: zone }).name, "@");
});

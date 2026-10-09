import { USER_RECORD_TYPES, type DNSRecord, type DNSRecordWrite, type UserDNSRecordType } from "@/types/dns-record";
export { USER_RECORD_TYPES } from "@/types/dns-record";

export const RECORD_TYPE_GUIDANCE: Record<UserDNSRecordType, { description: string; example: string; help: string }> = {
  A: { description: "Routes traffic to an IPv4 address", example: "192.0.2.10", help: "Enter an IPv4 address, for example 192.0.2.10." },
  AAAA: { description: "Routes traffic to an IPv6 address", example: "2001:db8::1", help: "Enter an IPv6 address, for example 2001:db8::1." },
  CNAME: { description: "Routes traffic to another domain name", example: "app.example.com", help: "Enter one hostname without a protocol. CNAME cannot be used at the zone apex." },
  TXT: { description: "Stores text values", example: "v=spf1 include:_spf.example.com ~all", help: "Enter text on one line per value field. JSON formatting and surrounding quotes are not required." },
  MX: { description: "Specifies mail servers", example: "10 mail.example.com", help: "Enter priority (0–65535) and mail server, for example 10 mail.example.com." },
  NS: { description: "Delegates a subdomain to name servers", example: "ns1.example.net", help: "Enter a name server hostname, for example ns1.example.net." },
  PTR: { description: "Maps an address name to a hostname", example: "host.example.com", help: "Enter a hostname target without a protocol." },
  SRV: { description: "Specifies service endpoints", example: "10 5 5060 sip.example.com", help: "Enter priority weight port target, for example 10 5 5060 sip.example.com. Numbers must be 0–65535." },
  CAA: { description: "Specifies certificate authorities", example: "0 issue letsencrypt.org", help: "Enter flags tag value, for example 0 issue letsencrypt.org. Flags must be 0–255." },
};
export interface DNSRecordFormValues { name: string; record_type: UserDNSRecordType; values: string[]; ttl: string }
export interface DNSRecordFormErrors { name?: string; record_type?: string; values?: string; ttl?: string; valueErrors?: (string | undefined)[] }
const hostLabel = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
const serviceLabel = /^_[a-z0-9](?:[a-z0-9-]{0,60}[a-z0-9])?$/;

export function recordName(raw: string, zoneName: string, type: UserDNSRecordType): { name: string; error?: string } {
  const value = raw.trim().toLowerCase();
  let name = value.replace(/\.$/, "");
  if (!value || value === "@") name = zoneName;
  else if (name !== zoneName && !name.endsWith(`.${zoneName}`)) {
    const srvRelative = type === "SRV" && name.split(".").length === 2 && name.split(".").every((label) => serviceLabel.test(label));
    if (!value.endsWith(".") && (!name.includes(".") || srvRelative)) name = `${name}.${zoneName}`;
    else return { name, error: `Enter a name within ${zoneName}. Use a single relative label or the full in-zone name.` };
  }
  if (value.length > 253 || name.length > 253 || name.split(".").some((label, index) =>
    !hostLabel.test(label) && !((type === "SRV" || type === "TXT") && serviceLabel.test(label)) && !(type !== "SRV" && index === 0 && label === "*"))) {
    return { name, error: "Use valid ASCII DNS labels of 1–63 characters, without spaces or a protocol. Maximum 253 characters." };
  }
  if (type === "CNAME" && name === zoneName) return { name, error: "CNAME records cannot be created at the hosted zone apex." };
  return { name };
}

export function initialRecordValues(zoneName: string, record?: DNSRecord): DNSRecordFormValues {
  const type = USER_RECORD_TYPES.find((type) => type === record?.record_type) ?? "A";
  let name = record?.name ?? "";
  if (name === zoneName) name = "@";
  else if (name.endsWith(`.${zoneName}`)) {
    const prefix = name.slice(0, -(zoneName.length + 1));
    if (!prefix.includes(".") || (type === "SRV" && prefix.split(".").length === 2 && prefix.split(".").every((label) => serviceLabel.test(label)))) name = prefix;
  }
  return { name, record_type: type, values: record ? [...record.values] : [""], ttl: String(record?.ttl ?? 300) };
}

function validIPv4(value: string): boolean {
  const parts = value.split(".");
  return parts.length === 4 && parts.every((part) => /^(0|[1-9][0-9]{0,2})$/.test(part) && Number(part) <= 255);
}
function validIPv6(value: string): boolean {
  // The standard URL parser validates bracketed IPv6, including compressed and IPv4-mapped forms.
  if (!value.includes(":") || !/^[0-9a-fA-F:.]+$/.test(value)) return false;
  try { return new URL(`http://[${value}]/`).hostname.startsWith("["); } catch { return false; }
}
function validHostname(value: string): boolean {
  const name = value.toLowerCase().replace(/\.$/, "");
  return name.length <= 253 && name.split(".").every((label) => hostLabel.test(label)) && !name.split(".").every((label) => /^[0-9]+$/.test(label));
}
function unsigned(value: string, maximum: number): boolean { return /^[0-9]{1,10}$/.test(value) && Number(value) <= maximum; }
function unquote(value: string): string { return value.startsWith('"') && value.endsWith('"') && value.length >= 2 ? value.slice(1, -1) : value; }

export function recordValueError(raw: string, type: UserDNSRecordType): string | undefined {
  const value = raw.trim();
  if (!value || /[\x00-\x1f\x7f]/.test(value)) return "Enter a nonblank value without line breaks or control characters.";
  if (raw.length > 4096) return "Use at most 4096 characters per value.";
  if (type === "A") return validIPv4(value) ? undefined : "Enter a valid IPv4 address, for example 192.0.2.10.";
  if (type === "AAAA") return validIPv6(value) ? undefined : "Enter a valid IPv6 address, for example 2001:db8::1.";
  if (type === "CNAME" || type === "NS" || type === "PTR") return validHostname(value) ? undefined : "Enter a valid ASCII hostname without a protocol or IP address.";
  if (type === "TXT") return unquote(value).trim() ? undefined : "TXT values cannot be blank.";
  const parts = value.split(/\s+/);
  if (type === "MX") return parts.length === 2 && unsigned(parts[0], 65535) && validHostname(parts[1]) ? undefined : "Use priority (0–65535) followed by a mail server hostname.";
  if (type === "SRV") return parts.length === 4 && parts.slice(0, 3).every((part) => unsigned(part, 65535)) && (parts[3] === "." || validHostname(parts[3]))
    ? undefined : "Use priority weight port target. Each number must be 0–65535; target must be a hostname or a dot.";
  const caa = /^(\S+)\s+(\S+)\s+(.+)$/.exec(value);
  return caa && unsigned(caa[1], 255) && /^[a-zA-Z0-9]{1,15}$/.test(caa[2]) && unquote(caa[3]).trim()
    ? undefined : "Use flags (0–255), an alphanumeric tag (1–15 characters), and a nonblank value.";
}

export function validateRecordForm(values: DNSRecordFormValues, zoneName: string): DNSRecordFormErrors {
  const errors: DNSRecordFormErrors = {};
  const normalized = recordName(values.name, zoneName, values.record_type);
  if (normalized.error) errors.name = normalized.error;
  if (!USER_RECORD_TYPES.includes(values.record_type)) errors.record_type = "Select a supported user record type.";
  if (!/^[0-9]+$/.test(values.ttl.trim()) || Number(values.ttl) < 1 || Number(values.ttl) > 2147483647) errors.ttl = "Enter a whole number from 1 to 2147483647 seconds.";
  if (!values.values.length || values.values.length > 100) errors.values = "Supply between 1 and 100 values.";
  else if (values.record_type === "CNAME" && values.values.length !== 1) errors.values = "CNAME records require exactly one value. Remove the extra values before saving.";
  const valueErrors = values.values.map((value) => recordValueError(value, values.record_type));
  if (valueErrors.some(Boolean)) errors.valueErrors = valueErrors;
  return errors;
}

export function recordPayload(values: DNSRecordFormValues, zoneName: string): DNSRecordWrite {
  return { name: recordName(values.name, zoneName, values.record_type).name, record_type: values.record_type,
    values: values.values.map((value) => value.trim()), ttl: Number(values.ttl), routing_policy: "SIMPLE" };
}

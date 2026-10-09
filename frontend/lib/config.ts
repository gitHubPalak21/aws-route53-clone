const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

// An empty base keeps /api requests on the browser's origin in production.
const parsedUrl = apiBaseUrl === "" ? null : new URL(apiBaseUrl);

if (
  parsedUrl &&
  (!["http:", "https:"].includes(parsedUrl.protocol) ||
    parsedUrl.username ||
    parsedUrl.password ||
    parsedUrl.search ||
    parsedUrl.hash)
) {
  throw new Error("NEXT_PUBLIC_API_BASE_URL must be an HTTP(S) base URL.");
}

export const config = {
  apiBaseUrl: parsedUrl?.toString().replace(/\/$/, "") ?? "",
} as const;

import { config } from "@/lib/config";
import type { ApiRequestOptions } from "@/types/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
    public readonly details: unknown = undefined,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(details: unknown, fallback: string): string {
  if (typeof details === "object" && details !== null) {
    if ("detail" in details && typeof details.detail === "string") {
      return details.detail;
    }
    if ("message" in details && typeof details.message === "string") {
      return details.message;
    }
  }
  return fallback;
}

/** Call a backend path. Empty responses return undefined; T is caller-supplied. */
export async function apiRequest<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T | undefined> {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new ApiError("API paths must start with a single slash.", null);
  }

  const { json, ...requestOptions } = options;
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (json !== undefined) headers.set("Content-Type", "application/json");

  let response: Response;
  let text: string;
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, {
      ...requestOptions,
      headers,
      credentials: "include",
      body: json === undefined ? undefined : JSON.stringify(json),
    });
    text = await response.text();
  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError("Unable to reach the API.", null, error);
  }

  let data: unknown;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      if (response.ok) {
        throw new ApiError("The API returned invalid JSON.", response.status, text);
      }
      data = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      errorMessage(data, `API request failed (${response.status}).`),
      response.status,
      data,
    );
  }

  return data as T | undefined;
}

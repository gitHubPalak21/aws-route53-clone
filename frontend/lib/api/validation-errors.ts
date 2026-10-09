import { ApiError } from "./client";

/** Extract sanitized FastAPI validation messages without rendering its raw JSON. */
export function validationFeedback(error: unknown): { fields: Record<string, string>; messages: string[] } {
  const fields: Record<string, string> = {};
  const messages: string[] = [];
  if (!(error instanceof ApiError) || error.status !== 422 || typeof error.details !== "object" || !error.details) {
    return { fields, messages };
  }
  if (!("detail" in error.details) || !Array.isArray(error.details.detail)) return { fields, messages };
  for (const issue of error.details.detail) {
    if (typeof issue !== "object" || issue === null || !("msg" in issue) || typeof issue.msg !== "string") continue;
    const message = issue.msg.replace(/^Value error, /, "");
    messages.push(message);
    if ("loc" in issue && Array.isArray(issue.loc)) {
      const field: unknown = issue.loc[1];
      if (typeof field === "string") fields[field] = message;
    }
  }
  return { fields, messages };
}

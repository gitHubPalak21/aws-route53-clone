import { ApiError } from "./client";
import { validationFeedback } from "./validation-errors";
import type { DNSRecordWrite } from "@/types/dns-record";

export function recordErrorFeedback(error: unknown, payload?: DNSRecordWrite): { message: string; fields: Record<string, string> } {
  const feedback = validationFeedback(error);
  if (feedback.messages.length) return { message: [...new Set(feedback.messages)].join(" "), fields: feedback.fields };
  let message = "The request could not be completed. Your entries have been kept. Try again.";
  if (error instanceof ApiError) {
    if (error.status === 404) message = "The record or hosted zone no longer exists, or you don't have access to it.";
    if (error.status === 409) message = /system-managed/i.test(error.message) ? error.message
      : payload ? `An ${payload.record_type} record for ${payload.name} already exists. Edit the existing record instead.` : error.message;
    if (error.status === null) message = "Unable to reach the API. Your entries have been kept. Check the connection and try again.";
  }
  return { message, fields: {} };
}

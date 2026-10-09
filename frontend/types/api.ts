export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type ApiRequestOptions = Omit<RequestInit, "body" | "credentials"> & {
  json?: JsonValue;
};

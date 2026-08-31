export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export type ApiCredential =
  | string
  | {
      kind: "reviewer";
      token: string;
    };

function credentialHeaders(credential: ApiCredential): Record<string, string> {
  if (typeof credential === "string") {
    return { "X-ScopeLock-Operator-Key": credential };
  }
  return { Authorization: `Bearer ${credential.token}` };
}

export async function apiRequest<T>(
  path: string,
  credential: ApiCredential,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...credentialHeaders(credential),
      ...(init?.headers ?? {}),
    },
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : `ScopeLock request failed (${response.status}).`;
    throw new ApiError(message, response.status);
  }
  return body as T;
}

export async function apiBlobRequest(
  path: string,
  credential: ApiCredential,
): Promise<Blob> {
  const response = await fetch(path, {
    cache: "no-store",
    headers: credentialHeaders(credential),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : `ScopeLock request failed (${response.status}).`,
      response.status,
    );
  }
  return response.blob();
}

export function correlationId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `ui-${Date.now()}`;
}

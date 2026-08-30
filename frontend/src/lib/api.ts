export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function apiRequest<T>(
  path: string,
  operatorKey: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-ScopeLock-Operator-Key": operatorKey,
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

export function correlationId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `ui-${Date.now()}`;
}

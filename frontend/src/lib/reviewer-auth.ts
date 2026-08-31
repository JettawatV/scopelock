import { readStoredJson, readStoredValue, writeStoredJson, writeStoredValue } from "@/lib/browser-storage";

export type FirebaseWebConfig = {
  apiKey: string;
  authDomain: string;
  projectId: string;
};

export type ReviewerToken = {
  token: string;
  refreshToken: string;
  email: string;
  expiresAt: number;
};

const TOKEN_STORAGE_KEY = "scopelock.reviewer.token";
const PENDING_EMAIL_STORAGE_KEY = "scopelock.reviewer.pendingEmail";

function firebaseUrl(config: FirebaseWebConfig, path: string): string {
  return `https://identitytoolkit.googleapis.com/v1/${path}?key=${encodeURIComponent(config.apiKey)}`;
}

async function firebaseRequest<T>(
  config: FirebaseWebConfig,
  path: string,
  body: Record<string, string | boolean>,
): Promise<T> {
  const response = await fetch(firebaseUrl(config, path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.error?.message;
    throw new Error(typeof message === "string" ? message.replaceAll("_", " ").toLowerCase() : "Firebase sign-in failed.");
  }
  return payload as T;
}

export async function loadReviewerConfig(): Promise<FirebaseWebConfig> {
  const response = await fetch("/api/reviewer/config", { cache: "no-store" });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.apiKey || !payload?.projectId) {
    throw new Error(typeof payload?.detail === "string" ? payload.detail : "Reviewer sign-in is not configured.");
  }
  return payload as FirebaseWebConfig;
}

export async function sendReviewerLink(
  config: FirebaseWebConfig,
  email: string,
): Promise<void> {
  const normalized = email.trim().toLowerCase();
  await firebaseRequest(config, "accounts:sendOobCode", {
    requestType: "EMAIL_SIGNIN",
    email: normalized,
    continueUrl: `${window.location.origin}/review/`,
    canHandleCodeInApp: true,
  });
  writeStoredValue("session", PENDING_EMAIL_STORAGE_KEY, normalized);
}

export async function completeReviewerLink(
  config: FirebaseWebConfig,
  email: string,
  oobCode: string,
): Promise<ReviewerToken> {
  const payload = await firebaseRequest<{
    email?: string;
    idToken: string;
    refreshToken: string;
    expiresIn: string;
  }>(config, "accounts:signInWithEmailLink", { email: email.trim().toLowerCase(), oobCode });
  const token: ReviewerToken = {
    token: payload.idToken,
    refreshToken: payload.refreshToken,
    email: (payload.email || email).trim().toLowerCase(),
    expiresAt: Date.now() + Number(payload.expiresIn || 3600) * 1000,
  };
  writeStoredJson("session", TOKEN_STORAGE_KEY, token);
  writeStoredValue("session", PENDING_EMAIL_STORAGE_KEY, "");
  return token;
}

export async function refreshReviewerToken(
  config: FirebaseWebConfig,
  current: ReviewerToken,
): Promise<ReviewerToken> {
  const response = await fetch(`https://securetoken.googleapis.com/v1/token?key=${encodeURIComponent(config.apiKey)}`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "refresh_token", refresh_token: current.refreshToken }),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.id_token || !payload?.refresh_token) {
    throw new Error("Reviewer session expired. Request a new email link.");
  }
  const token: ReviewerToken = {
    token: payload.id_token,
    refreshToken: payload.refresh_token,
    email: current.email,
    expiresAt: Date.now() + Number(payload.expires_in || 3600) * 1000,
  };
  writeStoredJson("session", TOKEN_STORAGE_KEY, token);
  return token;
}

export function storedReviewerToken(): ReviewerToken | null {
  const token = readStoredJson<ReviewerToken>("session", TOKEN_STORAGE_KEY);
  if (!token || !token.token || !token.refreshToken || !token.email || !Number.isFinite(token.expiresAt)) return null;
  return token;
}

export function pendingReviewerEmail(): string {
  return readStoredValue("session", PENDING_EMAIL_STORAGE_KEY) ?? "";
}

export function clearReviewerSession(): void {
  writeStoredValue("session", TOKEN_STORAGE_KEY, "");
  writeStoredValue("session", PENDING_EMAIL_STORAGE_KEY, "");
}

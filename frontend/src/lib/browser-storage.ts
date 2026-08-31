type StorageArea = "local" | "session";

function getStorage(area: StorageArea): Storage | null {
  if (typeof window === "undefined") return null;

  try {
    return area === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export function readStoredValue(area: StorageArea, key: string): string | null {
  const storage = getStorage(area);
  if (!storage) return null;

  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStoredValue(area: StorageArea, key: string, value: string): boolean {
  const storage = getStorage(area);
  if (!storage) return false;

  try {
    storage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

export function readStoredJson<T>(area: StorageArea, key: string): T | null {
  const raw = readStoredValue(area, key);
  if (raw === null) return null;

  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function writeStoredJson(area: StorageArea, key: string, value: unknown): boolean {
  try {
    return writeStoredValue(area, key, JSON.stringify(value));
  } catch {
    return false;
  }
}

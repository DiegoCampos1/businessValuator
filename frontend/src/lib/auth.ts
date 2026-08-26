const ACCESS_KEY = "bv_access";
const REFRESH_KEY = "bv_refresh";

let accessToken: string | null = null;

export function setTokens(access: string, refresh: string): void {
  accessToken = access;
  if (typeof window !== "undefined") {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  if (accessToken) return accessToken;
  accessToken = localStorage.getItem(ACCESS_KEY);
  return accessToken;
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function clearTokens(): void {
  accessToken = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

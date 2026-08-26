import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "./auth";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  const resp = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!resp.ok) {
    clearTokens();
    return null;
  }
  const data = await resp.json();
  setTokens(data.access_token, data.refresh_token);
  return data.access_token;
}

async function doFetch<T>(path: string, options: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, options);
  if (!resp.ok) {
    let detail: string = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let token = getAccessToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let resp = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (resp.status === 401) {
    token = await refreshAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
      resp = await fetch(`${API_URL}${path}`, { ...options, headers });
    }
  }
  if (!resp.ok) {
    let detail: string = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export interface Citation {
  source: string;
  title?: string;
  url: string;
}

export interface ChatEventHandlers {
  onStart?: (data: { company: string; sector_slug: string }) => void;
  onQuestion?: (data: { id: string; text: string }) => void;
  onToken?: (text: string) => void;
  onCitations?: (items: Citation[]) => void;
  onDone?: (conversationId: string) => void;
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  handlers: ChatEventHandlers,
): Promise<void> {
  let token = getAccessToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const buildBody = () =>
    JSON.stringify({ message, conversation_id: conversationId });

  let resp = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers,
    body: buildBody(),
  });

  if (resp.status === 401) {
    token = await refreshAccessToken();
    if (!token) throw new Error("Não autenticado");
    headers["Authorization"] = `Bearer ${token}`;
    resp = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers,
      body: buildBody(),
    });
  }

  if (!resp.ok || !resp.body) {
    let detail: string = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      let event: { type: string } & Record<string, unknown>;
      try {
        event = JSON.parse(payload);
      } catch {
        continue;
      }
      switch (event.type) {
        case "start":
          handlers.onStart?.(event as unknown as { company: string; sector_slug: string });
          break;
        case "question":
          handlers.onQuestion?.(event as unknown as { id: string; text: string });
          break;
        case "token":
          handlers.onToken?.(event.text as string);
          break;
        case "citations":
          handlers.onCitations?.((event.items as Citation[]) ?? []);
          break;
        case "done":
          handlers.onDone?.(event.conversation_id as string);
          break;
      }
    }
  }
}

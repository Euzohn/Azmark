import { useAuth } from "@/lib/auth-store";
import type {
  AuditLogList,
  Flight,
  FlightInput,
  FlightList,
  TokenResponse,
  User,
} from "@/lib/types";

// Empty by default → requests go to the same origin (/api/v1/...), and the
// Next.js server proxies them to the backend (see next.config.ts rewrites).
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = useAuth.getState().token;
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (response.status === 401) {
    useAuth.getState().clear();
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  register: (username: string, password: string, email?: string, display_name?: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password, email, display_name }),
    }),
  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<User>("/auth/me"),
  updateMe: (data: Partial<User>) =>
    request<User>("/auth/me", { method: "PATCH", body: JSON.stringify(data) }),
  changePassword: (current_password: string, new_password: string) =>
    request<User>("/auth/me/password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
  changeUsername: (current_password: string, new_username: string) =>
    request<User>("/auth/me/username", {
      method: "POST",
      body: JSON.stringify({ current_password, new_username }),
    }),

  listFlights: (params: { search?: string; page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<FlightList>(`/flights${suffix}`);
  },
  createFlight: (data: FlightInput) =>
    request<Flight>("/flights", { method: "POST", body: JSON.stringify(data) }),
  getFlight: (id: string) => request<Flight>(`/flights/${id}`),
  updateFlight: (id: string, data: FlightInput) =>
    request<Flight>(`/flights/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteFlight: (id: string) => request<void>(`/flights/${id}`, { method: "DELETE" }),

  listAuditLogs: (params: { page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<AuditLogList>(`/audit-logs${suffix}`);
  },
};

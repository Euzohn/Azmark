import { useAuth } from "@/lib/auth-store";
import type {
  AiSettingsRead,
  AiSettingsWrite,
  Airline,
  Airport,
  AuditLogList,
  Flight,
  FlightInput,
  FlightList,
  FlightLookup,
  FlightNumberLookup,
  ProviderKeysRead,
  ProviderKeyStatus,
  TokenResponse,
  Trip,
  TripDetail,
  TripInput,
  TripList,
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

  listTrips: (params: { page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<TripList>(`/trips${suffix}`);
  },
  createTrip: (data: TripInput) =>
    request<Trip>("/trips", { method: "POST", body: JSON.stringify(data) }),
  getTrip: (id: string) => request<TripDetail>(`/trips/${id}`),
  updateTrip: (id: string, data: Partial<TripInput>) =>
    request<Trip>(`/trips/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTrip: (id: string) => request<void>(`/trips/${id}`, { method: "DELETE" }),

  searchAirports: (query: string) =>
    request<Airport[]>(`/reference/airports?q=${encodeURIComponent(query)}`),
  searchAirlines: (query: string) =>
    request<Airline[]>(`/reference/airlines?q=${encodeURIComponent(query)}`),
  getAirlineByCode: (iata: string) =>
    request<Airline>(`/reference/airlines/${encodeURIComponent(iata)}`),
  lookupFlightNumber: (number: string) =>
    request<FlightNumberLookup>(`/reference/flight-lookup?number=${encodeURIComponent(number)}`),
  lookupFlight: (data: { flight_number: string; date?: string; provider?: string }) =>
    request<FlightLookup>("/flights/lookup", { method: "POST", body: JSON.stringify(data) }),

  listProviderKeys: () => request<ProviderKeysRead>("/settings/provider-keys"),
  setProviderKey: (provider: string, api_key: string) =>
    request<ProviderKeyStatus>(`/settings/provider-keys/${provider}`, {
      method: "PUT",
      body: JSON.stringify({ api_key }),
    }),
  deleteProviderKey: (provider: string) =>
    request<void>(`/settings/provider-keys/${provider}`, { method: "DELETE" }),

  getAiSettings: () => request<AiSettingsRead>("/settings/ai"),
  setAiSettings: (data: AiSettingsWrite) =>
    request<AiSettingsRead>("/settings/ai", { method: "PUT", body: JSON.stringify(data) }),
  deleteAiSettings: () => request<void>("/settings/ai", { method: "DELETE" }),

  listAuditLogs: (params: { page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<AuditLogList>(`/audit-logs${suffix}`);
  },
};

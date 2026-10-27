import { useAuth } from "@/lib/auth-store";
import type {
  AdminAuditLogList,
  AdminSystem,
  AdminUser,
  AdminUserList,
  AiChatResponse,
  Attachment,
  AttachmentList,
  AiSettingsRead,
  AiSettingsWrite,
  AiStreamEvent,
  Airline,
  Airport,
  AuditLogList,
  DashboardRead,
  DataSourceList,
  Flight,
  FlightFilters,
  FlightInput,
  FlightList,
  FlightLookup,
  LookupAllResponse,
  FlightNumberLookup,
  ImportPreview,
  ImportResult,
  MapRoutesRead,
  OtherTransport,
  OtherTransportInput,
  OtherTransportList,
  ProviderKeysRead,
  ProviderKeyStatus,
  RecordFilters,
  RecordList,
  StatisticsRead,
  TimelineRecord,
  TokenResponse,
  Train,
  TrainInput,
  TrainList,
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
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = useAuth.getState().token;
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (response.status === 401) {
    useAuth.getState().clear();
  }

  if (!response.ok) {
    let detail = response.statusText;
    let payload: unknown;
    try {
      const body = (await response.json()) as { detail?: unknown };
      payload = body.detail;
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (
        body.detail &&
        typeof body.detail === "object" &&
        typeof (body.detail as { message?: unknown }).message === "string"
      ) {
        detail = (body.detail as { message: string }).message;
      }
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(response.status, detail, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function fetchBlob(path: string): Promise<Blob> {
  const token = useAuth.getState().token;
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (response.status === 401) {
    useAuth.getState().clear();
  }
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }
  return response.blob();
}

function importForm(file: File, mapping?: Record<string, string>): FormData {
  const form = new FormData();
  form.append("file", file);
  if (mapping && Object.values(mapping).some(Boolean)) {
    form.append("mapping", JSON.stringify(mapping));
  }
  return form;
}

function attachmentForm(
  resourceType: string,
  resourceId: string,
  file: File,
): FormData {
  const form = new FormData();
  form.append("resource_type", resourceType);
  form.append("resource_id", resourceId);
  form.append("file", file);
  return form;
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
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  deleteAccount: (password: string) =>
    request<void>("/auth/me/delete", {
      method: "POST",
      body: JSON.stringify({ password }),
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

  listRecords: (params: RecordFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.type) query.set("type", params.type);
    if (params.status) query.set("status", params.status);
    if (params.carrier) query.set("carrier", params.carrier);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.sort) query.set("sort", params.sort);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<RecordList>(`/records${suffix}`);
  },
  listFlights: (params: FlightFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    if (params.cabin_class) query.set("cabin_class", params.cabin_class);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<FlightList>(`/flights${suffix}`);
  },
  createFlight: (data: FlightInput, force = false) =>
    request<Flight>(`/flights${force ? "?force=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getFlight: (id: string) => request<Flight>(`/flights/${id}`),
  updateFlight: (id: string, data: FlightInput) =>
    request<Flight>(`/flights/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteFlight: (id: string) => request<void>(`/flights/${id}`, { method: "DELETE" }),

  listTrains: (params: FlightFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    if (params.cabin_class) query.set("cabin_class", params.cabin_class);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<TrainList>(`/trains${suffix}`);
  },
  createTrain: (data: TrainInput, force = false) =>
    request<Train>(`/trains${force ? "?force=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getTrain: (id: string) => request<Train>(`/trains/${id}`),
  updateTrain: (id: string, data: TrainInput) =>
    request<Train>(`/trains/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTrain: (id: string) => request<void>(`/trains/${id}`, { method: "DELETE" }),

  listOtherTransports: (params: FlightFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<OtherTransportList>(`/other-transports${suffix}`);
  },
  createOtherTransport: (data: OtherTransportInput, force = false) =>
    request<OtherTransport>(`/other-transports${force ? "?force=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getOtherTransport: (id: string) => request<OtherTransport>(`/other-transports/${id}`),
  updateOtherTransport: (id: string, data: OtherTransportInput) =>
    request<OtherTransport>(`/other-transports/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteOtherTransport: (id: string) =>
    request<void>(`/other-transports/${id}`, { method: "DELETE" }),

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
  reorderTripItems: (tripId: string, itemIds: string[]) =>
    request<void>(`/trips/${tripId}/items/order`, {
      method: "PUT",
      body: JSON.stringify({ item_ids: itemIds }),
    }),
  updateTripItem: (
    tripId: string,
    itemId: string,
    data: { sort_order?: number; start_at?: string | null; end_at?: string | null },
  ) =>
    request<void>(`/trips/${tripId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteTrip: (id: string) => request<void>(`/trips/${id}`, { method: "DELETE" }),

  searchAirports: (query: string) =>
    request<Airport[]>(`/reference/airports?q=${encodeURIComponent(query)}`),
  searchAirlines: (query: string) =>
    request<Airline[]>(`/reference/airlines?q=${encodeURIComponent(query)}`),
  getAirlineByCode: (iata: string) =>
    request<Airline>(`/reference/airlines/${encodeURIComponent(iata)}`),
  getAirportByIata: (iata: string) =>
    request<Airport>(`/reference/airports/${encodeURIComponent(iata)}`),
  lookupFlightNumber: (number: string) =>
    request<FlightNumberLookup>(`/reference/flight-lookup?number=${encodeURIComponent(number)}`),
  lookupFlight: (data: { flight_number: string; date?: string; provider?: string }) =>
    request<FlightLookup>("/flights/lookup", { method: "POST", body: JSON.stringify(data) }),
  lookupFlightAll: (data: { flight_number: string; date?: string }) =>
    request<LookupAllResponse>("/flights/lookup-all", { method: "POST", body: JSON.stringify(data) }),

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

  listDataSources: (params: { source_type?: string; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.source_type) query.set("source_type", params.source_type);
    if (params.limit) query.set("limit", String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<DataSourceList>(`/data-sources${suffix}`);
  },
  deleteDataSource: (id: string) =>
    request<void>(`/data-sources/${id}`, { method: "DELETE" }),

  listAdminUsers: (params: { search?: string; page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<AdminUserList>(`/admin/users${suffix}`);
  },
  updateAdminUser: (id: string, data: { role?: string; status?: string }) =>
    request<AdminUser>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  getAdminSystem: () => request<AdminSystem>("/admin/system"),
  listAdminLogs: (params: { page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<AdminAuditLogList>(`/admin/logs${suffix}`);
  },

  getDashboard: () => request<DashboardRead>("/dashboard"),
  getStatistics: () => request<StatisticsRead>("/statistics"),
  getTimeline: () => request<TimelineRecord[]>("/timeline"),
  getMapRoutes: () => request<MapRoutesRead>("/map/routes"),

  listAttachments: (resourceType: string, resourceId: string) =>
    request<AttachmentList>(
      `/attachments?resource_type=${encodeURIComponent(resourceType)}&resource_id=${encodeURIComponent(resourceId)}`,
    ),
  uploadAttachment: (resourceType: string, resourceId: string, file: File) =>
    request<Attachment>("/attachments", {
      method: "POST",
      body: attachmentForm(resourceType, resourceId, file),
    }),
  deleteAttachment: (id: string) =>
    request<void>(`/attachments/${id}`, { method: "DELETE" }),
  downloadAttachment: (id: string) => fetchBlob(`/attachments/${id}/download`),
  exportData: (format: "json" | "csv", includeSensitive = false) =>
    fetchBlob(`/export?format=${format}&include_sensitive=${includeSensitive}`),
  importTemplate: (format: "json" | "csv" = "csv") =>
    fetchBlob(`/import/template?format=${format}`),
  previewImport: (file: File, mapping?: Record<string, string>) =>
    request<ImportPreview>("/import/preview", {
      method: "POST",
      body: importForm(file, mapping),
    }),
  importData: (file: File, mapping?: Record<string, string>) =>
    request<ImportResult>("/import", {
      method: "POST",
      body: importForm(file, mapping),
    }),

  chatAi: (message: string, image?: string | null) =>
    request<AiChatResponse>("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message, image }),
    }),

  chatAiStream: async function* (
    message: string,
    image?: string | null,
  ): AsyncGenerator<AiStreamEvent> {
    const token = useAuth.getState().token;
    const response = await fetch(`${API_BASE}/api/v1/ai/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, image }),
    });

    if (response.status === 401) {
      useAuth.getState().clear();
      throw new ApiError(401, "Unauthorized");
    }

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = (await response.json()) as { detail?: string };
        detail = body.detail ?? detail;
      } catch {
        // ignore parse errors, fall back to statusText
      }
      throw new ApiError(response.status, detail);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new ApiError(0, "No response body");
    }

    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          yield JSON.parse(trimmed) as AiStreamEvent;
        } catch {
          // ignore malformed lines
        }
      }
    }
  },
};

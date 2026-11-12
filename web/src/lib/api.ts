import { useAuth } from "@/lib/auth-store";
import type {
  AdminAuditLogList,
  AdminSettings,
  AdminSettingsUpdateInput,
  AdminSystem,
  AdminUser,
  AdminUserCreateInput,
  AdminUserList,
  AiChatResponse,
  AiHistoryMessage,
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
  HotelFilters,
  FlightInput,
  FlightList,
  FlightLookup,
  LookupAllResponse,
  FlightNumberLookup,
  ImportPreview,
  ImportResult,
  MapRoutesRead,
  WrappedRead,
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
  AccessTokenList,
  AccessTokenCreated,
  AccessTokenScope,
  AuthConfig,
  CaptchaChallenge,
  Hotel,
  HotelGeocodeRead,
  HotelInput,
  HotelList,
  PendingAction,
  PendingActionList,
  Expense,
  ExpenseFilters,
  ExpenseInput,
  ExpenseList,
  Note,
  NoteFilters,
  NoteInput,
  NoteList,
  Activity,
  ActivityFilters,
  ActivityInput,
  ActivityList,
  Place,
  PlaceFilters,
  PlaceInput,
  PlaceList,
  TripItem,
  TripItemCreate,
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

function idempotencyHeaders(key?: string): Record<string, string> {
  return key ? { "Idempotency-Key": key } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {  const token = useAuth.getState().token;
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
  register: (payload: {
    username: string;
    password: string;
    email?: string;
    display_name?: string;
    captcha_token?: string;
    captcha_answer?: string;
  }) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAuthConfig: () => request<AuthConfig>("/auth/config"),
  getCaptcha: () => request<CaptchaChallenge>("/auth/captcha"),
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
  getRecord: (id: string) => request<Flight>(`/records/${id}`),
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

  listHotels: (params: HotelFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.sort) query.set("sort", params.sort);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<HotelList>(`/hotels${suffix}`);
  },
  createHotel: (data: HotelInput, force = false) =>
    request<Hotel>(`/hotels${force ? "?force=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getHotel: (id: string) => request<Hotel>(`/hotels/${id}`),
  updateHotel: (id: string, data: HotelInput) =>
    request<Hotel>(`/hotels/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteHotel: (id: string) => request<void>(`/hotels/${id}`, { method: "DELETE" }),
  geocodeHotel: (id: string) =>
    request<HotelGeocodeRead>(`/hotels/${id}/geocode`, { method: "POST" }),

  listExpenses: (params: ExpenseFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.category) query.set("category", params.category);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.source_type) query.set("source_type", params.source_type);
    if (params.source_id) query.set("source_id", params.source_id);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.sort) query.set("sort", params.sort);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<ExpenseList>(`/expenses${suffix}`);
  },
  createExpense: (data: ExpenseInput, idempotencyKey?: string) =>
    request<Expense>("/expenses", {
      method: "POST",
      body: JSON.stringify(data),
      ...(idempotencyKey ? { headers: { "Idempotency-Key": idempotencyKey } } : {}),
    }),
  getExpense: (id: string) => request<Expense>(`/expenses/${id}`),
  updateExpense: (id: string, data: ExpenseInput) =>
    request<Expense>(`/expenses/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteExpense: (id: string) => request<void>(`/expenses/${id}`, { method: "DELETE" }),

  listNotes: (params: NoteFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.sort) query.set("sort", params.sort);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<NoteList>(`/notes${suffix}`);
  },
  createNote: (data: NoteInput) =>
    request<Note>("/notes", { method: "POST", body: JSON.stringify(data) }),
  getNote: (id: string) => request<Note>(`/notes/${id}`),
  updateNote: (id: string, data: NoteInput) =>
    request<Note>(`/notes/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteNote: (id: string) => request<void>(`/notes/${id}`, { method: "DELETE" }),

  listPlaces: (params: PlaceFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.type) query.set("type", params.type);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<PlaceList>(`/places${suffix}`);
  },
  createPlace: (data: PlaceInput) =>
    request<Place>("/places", { method: "POST", body: JSON.stringify(data) }),
  getPlace: (id: string) => request<Place>(`/places/${id}`),
  updatePlace: (id: string, data: PlaceInput) =>
    request<Place>(`/places/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deletePlace: (id: string) => request<void>(`/places/${id}`, { method: "DELETE" }),

  listActivities: (params: ActivityFilters = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.type) query.set("type", params.type);
    if (params.trip_id) query.set("trip_id", params.trip_id);
    if (params.place_id) query.set("place_id", params.place_id);
    if (params.sort) query.set("sort", params.sort);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<ActivityList>(`/activities${suffix}`);
  },
  createActivity: (data: ActivityInput, idempotencyKey?: string) =>
    request<Activity>("/activities", {
      method: "POST",
      body: JSON.stringify(data),
      headers: idempotencyHeaders(idempotencyKey),
    }),
  getActivity: (id: string) => request<Activity>(`/activities/${id}`),
  updateActivity: (id: string, data: ActivityInput) =>
    request<Activity>(`/activities/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteActivity: (id: string) => request<void>(`/activities/${id}`, { method: "DELETE" }),

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
  getTrip: (id: string, direction: "asc" | "desc" = "asc") =>
    request<TripDetail>(`/trips/${id}?direction=${direction}`),
  updateTrip: (id: string, data: Partial<TripInput>, direction: "asc" | "desc" = "asc") =>
    request<Trip>(`/trips/${id}?direction=${direction}`, { method: "PATCH", body: JSON.stringify(data) }),
  reorderTripItems: (tripId: string, itemIds: string[]) =>
    request<void>(`/trips/${tripId}/items/order`, {
      method: "PUT",
      body: JSON.stringify({ item_ids: itemIds }),
    }),
  updateTripItem: (tripId: string, itemId: string, data: { sort_order: number }) =>
    request<void>(`/trips/${tripId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  repairTripTimeline: (tripId: string) =>
    request<{ added: number; fixed: number; removed: number }>(
      `/trips/${tripId}/timeline/repair`,
      { method: "POST" },
    ),
  addTripItem: (tripId: string, data: TripItemCreate, idempotencyKey?: string) =>
    request<TripItem>(`/trips/${tripId}/items`, {
      method: "POST",
      body: JSON.stringify(data),
      headers: idempotencyHeaders(idempotencyKey),
    }),
  deleteTripItem: (tripId: string, itemId: string) =>
    request<void>(`/trips/${tripId}/items/${itemId}`, { method: "DELETE" }),
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

  listAccessTokens: () => request<AccessTokenList>("/tokens"),
  createAccessToken: (data: {
    name: string;
    scope: AccessTokenScope;
    expires_in_days: number | null;
  }) => request<AccessTokenCreated>("/tokens", { method: "POST", body: JSON.stringify(data) }),
  revokeAccessToken: (id: string) =>
    request<void>(`/tokens/${id}/revoke`, { method: "POST" }),
  deleteAccessToken: (id: string) => request<void>(`/tokens/${id}`, { method: "DELETE" }),

  listPendingActions: (params: { status?: string; page?: number; page_size?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<PendingActionList>(`/pending-actions${suffix}`);
  },
  getPendingAction: (id: string) => request<PendingAction>(`/pending-actions/${id}`),
  confirmPendingAction: (id: string, force: boolean) =>
    request<PendingAction>(`/pending-actions/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ force }),
    }),
  rejectPendingAction: (id: string) =>
    request<PendingAction>(`/pending-actions/${id}/reject`, { method: "POST" }),

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
  updateAdminUser: (id: string, data: { role?: string; status?: string; new_password?: string }) =>
    request<AdminUser>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  createAdminUser: (data: AdminUserCreateInput) =>
    request<AdminUser>("/admin/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getAdminSettings: () => request<AdminSettings>("/admin/settings"),
  updateAdminSettings: (data: AdminSettingsUpdateInput) =>
    request<AdminSettings>("/admin/settings", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  testAdminEmail: (to?: string) =>
    request<{ ok: boolean }>("/admin/settings/test-email", {
      method: "POST",
      body: JSON.stringify(to ? { to } : {}),
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
  getWrapped: (year?: number) =>
    request<WrappedRead>(
      year ? `/statistics/wrapped?year=${encodeURIComponent(String(year))}` : "/statistics/wrapped",
    ),
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
  importData: (file: File, mapping?: Record<string, string>, confirmPartial = false) =>
    request<ImportResult>("/import", {
      method: "POST",
      body: (() => {
        const form = importForm(file, mapping);
        if (confirmPartial) form.append("confirm_partial", "true");
        return form;
      })(),
    }),

  chatAi: (message: string, image?: string | null, history?: AiHistoryMessage[]) =>
    request<AiChatResponse>("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message, image, history }),
    }),

  chatAiStream: async function* (
    message: string,
    image?: string | null,
    history?: AiHistoryMessage[],
  ): AsyncGenerator<AiStreamEvent> {
    const token = useAuth.getState().token;
    const response = await fetch(`${API_BASE}/api/v1/ai/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, image, history }),
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

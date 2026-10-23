export interface User {
  id: string;
  username: string;
  email: string | null;
  display_name: string | null;
  role: string;
  locale: string;
  timezone: string;
  currency: string;
}

export interface Flight {
  id: string;
  user_id: string;
  type: string;
  status: string;
  departure_time: string | null;
  arrival_time: string | null;
  actual_departure_time: string | null;
  actual_arrival_time: string | null;
  departure_timezone: string | null;
  arrival_timezone: string | null;
  origin: string | null;
  destination: string | null;
  carrier: string | null;
  airline_code: string | null;
  service_number: string | null;
  cabin_class: string | null;
  seat: string | null;
  seat_type: string | null;
  departure_terminal: string | null;
  departure_gate: string | null;
  arrival_terminal: string | null;
  arrival_gate: string | null;
  check_in_desk: string | null;
  baggage_belt: string | null;
  aircraft_model: string | null;
  aircraft_reg: string | null;
  booking_reference: string | null;
  ticket_number: string | null;
  purchase_credential_type: string | null;
  purchase_credential: string | null;
  price: string | null;
  currency: string | null;
  distance: string | null;
  notes: string | null;
  trip_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlightInput {
  status?: string;
  departure_time?: string | null;
  arrival_time?: string | null;
  actual_departure_time?: string | null;
  actual_arrival_time?: string | null;
  departure_timezone?: string | null;
  arrival_timezone?: string | null;
  origin?: string | null;
  destination?: string | null;
  carrier?: string | null;
  airline_code?: string | null;
  service_number?: string | null;
  cabin_class?: string | null;
  seat?: string | null;
  seat_type?: string | null;
  departure_terminal?: string | null;
  departure_gate?: string | null;
  arrival_terminal?: string | null;
  arrival_gate?: string | null;
  check_in_desk?: string | null;
  baggage_belt?: string | null;
  aircraft_model?: string | null;
  aircraft_reg?: string | null;
  booking_reference?: string | null;
  ticket_number?: string | null;
  purchase_credential_type?: string | null;
  purchase_credential?: string | null;
  price?: string | null;
  currency?: string | null;
  distance?: string | null;
  notes?: string | null;
  trip_id?: string | null;
}

export interface FlightList {
  items: Flight[];
  total: number;
  page: number;
  page_size: number;
}

export interface Train {
  id: string;
  user_id: string;
  type: string;
  status: string;
  departure_time: string | null;
  arrival_time: string | null;
  actual_departure_time: string | null;
  actual_arrival_time: string | null;
  departure_timezone: string | null;
  arrival_timezone: string | null;
  origin: string | null;
  destination: string | null;
  carrier: string | null;
  service_number: string | null;
  cabin_class: string | null;
  seat: string | null;
  train_type: string | null;
  carriage: string | null;
  seat_type: string | null;
  ticket_type: string | null;
  departure_gate: string | null;
  arrival_gate: string | null;
  booking_reference: string | null;
  ticket_number: string | null;
  purchase_credential_type: string | null;
  purchase_credential: string | null;
  price: string | null;
  currency: string | null;
  distance: string | null;
  notes: string | null;
  trip_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrainInput {
  status?: string;
  departure_time?: string | null;
  arrival_time?: string | null;
  actual_departure_time?: string | null;
  actual_arrival_time?: string | null;
  departure_timezone?: string | null;
  arrival_timezone?: string | null;
  origin?: string | null;
  destination?: string | null;
  carrier?: string | null;
  service_number?: string | null;
  cabin_class?: string | null;
  seat?: string | null;
  train_type?: string | null;
  carriage?: string | null;
  seat_type?: string | null;
  ticket_type?: string | null;
  departure_gate?: string | null;
  arrival_gate?: string | null;
  booking_reference?: string | null;
  ticket_number?: string | null;
  purchase_credential_type?: string | null;
  purchase_credential?: string | null;
  price?: string | null;
  currency?: string | null;
  distance?: string | null;
  notes?: string | null;
  trip_id?: string | null;
}

export interface TrainList {
  items: Train[];
  total: number;
  page: number;
  page_size: number;
}

export interface OtherTransport {
  id: string;
  user_id: string;
  type: string;
  status: string;
  departure_time: string | null;
  arrival_time: string | null;
  actual_departure_time: string | null;
  actual_arrival_time: string | null;
  departure_timezone: string | null;
  arrival_timezone: string | null;
  origin: string | null;
  destination: string | null;
  carrier: string | null;
  service_number: string | null;
  vehicle_type: string | null;
  seat: string | null;
  departure_gate: string | null;
  arrival_gate: string | null;
  booking_reference: string | null;
  ticket_number: string | null;
  purchase_credential_type: string | null;
  purchase_credential: string | null;
  price: string | null;
  currency: string | null;
  distance: string | null;
  notes: string | null;
  trip_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface OtherTransportInput {
  status?: string;
  departure_time?: string | null;
  arrival_time?: string | null;
  actual_departure_time?: string | null;
  actual_arrival_time?: string | null;
  departure_timezone?: string | null;
  arrival_timezone?: string | null;
  origin?: string | null;
  destination?: string | null;
  carrier?: string | null;
  service_number?: string | null;
  vehicle_type?: string | null;
  seat?: string | null;
  departure_gate?: string | null;
  arrival_gate?: string | null;
  booking_reference?: string | null;
  ticket_number?: string | null;
  purchase_credential_type?: string | null;
  purchase_credential?: string | null;
  price?: string | null;
  currency?: string | null;
  distance?: string | null;
  notes?: string | null;
  trip_id?: string | null;
}

export interface OtherTransportList {
  items: OtherTransport[];
  total: number;
  page: number;
  page_size: number;
}

export type TimelineRecord = Flight | Train | OtherTransport;

export interface FlightFilters {
  search?: string;
  status?: string;
  cabin_class?: string;
  trip_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export type RecordType = "flight" | "train" | "other";
export type RecordSort = "newest" | "oldest" | "departure" | "arrival" | "created";

export interface RecordFilters {
  search?: string;
  type?: RecordType;
  status?: string;
  carrier?: string;
  trip_id?: string;
  date_from?: string;
  date_to?: string;
  sort?: RecordSort;
  page?: number;
  page_size?: number;
}

export interface RecordList {
  items: TimelineRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface Trip {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  start_date: string | null;
  end_date: string | null;
  cover_image: string | null;
  origin: string | null;
  destination: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TripInput {
  name: string;
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  cover_image?: string | null;
  origin?: string | null;
  destination?: string | null;
  status?: string;
}

export interface TripItem {
  id: string;
  item_type: string;
  item_id: string;
  sort_order: number;
  start_at: string | null;
  end_at: string | null;
  record: TimelineRecord | null;
}

export interface TripDetail extends Trip {
  records: TimelineRecord[];
  items: TripItem[];
}

export interface Attachment {
  id: string;
  resource_type: string;
  resource_id: string;
  filename: string;
  mime_type: string;
  size: number;
  created_at: string;
}

export interface AttachmentList {
  items: Attachment[];
  total: number;
}

export interface TripList {
  items: Trip[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditLog {
  id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AdminUser {
  id: string;
  username: string;
  email: string | null;
  display_name: string | null;
  role: "USER" | "ADMIN";
  status: "ACTIVE" | "DISABLED";
  records: number;
  trips: number;
  created_at: string;
}

export interface AdminUserList {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminSystem {
  version: string;
  users: number;
  active_users: number;
  admins: number;
  records: number;
  trips: number;
  audit_logs: number;
}

export interface AdminAuditLog {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface AdminAuditLogList {
  items: AdminAuditLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface Airport {
  iata: string;
  icao: string | null;
  name: string;
  name_zh: string | null;
  city: string | null;
  city_zh: string | null;
  country: string | null;
  lat: number | null;
  lon: number | null;
}

export interface Airline {
  iata: string;
  icao: string | null;
  name: string;
  name_zh: string | null;
  country: string | null;
  alliance: string | null;
}

export interface FlightNumberLookup {
  flight_number: string;
  airline_code: string | null;
  airline: Airline | null;
}

export interface FlightLookup {
  flight_number: string;
  airline_code: string | null;
  airline_name: string | null;
  airline_name_zh: string | null;
  origin_iata: string | null;
  destination_iata: string | null;
  origin_name: string | null;
  destination_name: string | null;
  departure_time: string | null;
  arrival_time: string | null;
  actual_departure_time: string | null;
  actual_arrival_time: string | null;
  departure_terminal: string | null;
  departure_gate: string | null;
  arrival_terminal: string | null;
  arrival_gate: string | null;
  check_in_desk: string | null;
  baggage_belt: string | null;
  aircraft_model: string | null;
  aircraft_reg: string | null;
  departure_timezone: string | null;
  arrival_timezone: string | null;
  aircraft: string | null;
  status: string | null;
  distance: number | null;
  source: string | null;
}

export interface ProviderLookupResult {
  provider: string;
  data: FlightLookup | null;
}

export interface LookupAllResponse {
  flight_number: string;
  results: ProviderLookupResult[];
}

export interface ProviderKeyStatus {
  provider: string;
  configured: boolean;
}

export interface ProviderKeysRead {
  providers: ProviderKeyStatus[];
}

export interface AiSettingsRead {
  provider: string;
  model: string;
  base_url: string | null;
  configured: boolean;
  temperature: number | null;
  context_limit: number | null;
}

export interface AiSettingsWrite {
  provider: string;
  model: string;
  base_url?: string | null;
  api_key?: string | null;
  temperature?: number | null;
  context_limit?: number | null;
}

export interface DashboardStats {
  countries: number;
  cities: number;
  journeys: number;
  distance_km: number;
  flights: number;
  trains: number;
  transports: number;
  trips: number;
}

export interface DashboardRecord {
  id: string;
  type: string;
  status: string;
  origin: string | null;
  destination: string | null;
  service_number: string | null;
  carrier: string | null;
  airline_code: string | null;
  departure_time: string | null;
  arrival_time: string | null;
  trip_id: string | null;
}

export interface DashboardRead {
  stats: DashboardStats;
  recent: DashboardRecord[];
  upcoming: DashboardRecord | null;
  by_month: BreakdownItem[];
}

export interface BreakdownItem {
  label: string;
  name: string | null;
  count: number;
}

export interface StatisticsTotals {
  countries: number;
  cities: number;
  distance_km: number;
  trips: number;
  flights: number;
  trains: number;
  transports: number;
}

export interface StatisticsRead {
  totals: StatisticsTotals;
  by_year: BreakdownItem[];
  by_month: BreakdownItem[];
  by_day: BreakdownItem[];
  by_airline: BreakdownItem[];
  by_alliance: BreakdownItem[];
  by_airport: BreakdownItem[];
  by_aircraft: BreakdownItem[];
  by_cabin: BreakdownItem[];
  by_seat_type: BreakdownItem[];
  by_train_operator: BreakdownItem[];
  by_train_type: BreakdownItem[];
  by_station: BreakdownItem[];
  by_train_class: BreakdownItem[];
  by_train_seat_type: BreakdownItem[];
}

export interface MapPoint {
  code: string | null;
  name: string | null;
  name_zh: string | null;
  city: string | null;
  city_zh: string | null;
  country: string | null;
  lat: number | null;
  lon: number | null;
}

export interface MapRoute {
  id: string;
  type: string;
  status: string;
  service_number: string | null;
  airline_code: string | null;
  carrier: string | null;
  departure_time: string | null;
  origin: MapPoint;
  destination: MapPoint;
  distance_km: number | null;
}

export interface MapRoutesRead {
  items: MapRoute[];
  total: number;
}

export interface AiProposal {
  id: string;
  action: string;
  record_type: string;
  summary: string;
  data: Record<string, unknown>;
  status?: "pending" | "saved" | "cancelled" | "duplicate";
  existingRecordId?: string;
}

export interface AiChatResponse {
  reply: string;
  proposals: AiProposal[];
}

export interface AiStreamEvent {
  type: "text" | "proposals" | "done" | "error";
  content?: string;
  proposals?: AiProposal[];
  message?: string;
}

export interface ImportRowError {
  row: number;
  field: string | null;
  message: string;
}

export interface ImportDuplicate {
  row: number;
  signature: string;
}

export interface ImportPreview {
  format: string;
  columns: string[];
  field_mapping: Record<string, string>;
  target_fields: string[];
  total: number;
  valid: number;
  duplicate_count: number;
  error_count: number;
  errors: ImportRowError[];
  duplicates: ImportDuplicate[];
  rows: Record<string, unknown>[];
  truncated: boolean;
}

export interface ImportResult {
  imported: number;
  skipped_duplicates: number;
  failed: number;
  trips_created: number;
  errors: ImportRowError[];
}

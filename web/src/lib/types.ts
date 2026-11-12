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

export interface HotelFilters {
  search?: string;
  status?: string;
  trip_id?: string;
  date_from?: string;
  date_to?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export type HotelStatus = "scheduled" | "completed" | "cancelled";

export interface Hotel {
  id: string;
  user_id: string;
  hotel: string;
  check_in: string;
  check_out: string | null;
  room_type: string | null;
  room_number: string | null;
  booking_reference: string | null;
  price: number | null;
  currency: string | null;
  address: string | null;
  notes: string | null;
  trip_id: string | null;
  status: string;
  lat: number | null;
  lon: number | null;
  created_at: string;
  updated_at: string;
}

export interface HotelInput {
  hotel?: string;
  check_in?: string;
  check_out?: string | null;
  room_type?: string | null;
  room_number?: string | null;
  booking_reference?: string | null;
  price?: number | null;
  currency?: string | null;
  address?: string | null;
  notes?: string | null;
  trip_id?: string | null;
  status?: string;
  lat?: number | null;
  lon?: number | null;
}

export interface HotelList {
  items: Hotel[];
  total: number;
  page: number;
  page_size: number;
}

export interface HotelGeocodeRead {
  hotel: Hotel;
  matched_address: string | null;
}

export type ExpenseCategory =
  | "transport"
  | "accommodation"
  | "food"
  | "shopping"
  | "entertainment"
  | "other";

export type ExpenseSourceType = "transport" | "hotel" | "activity";

export interface Expense {
  id: string;
  user_id: string;
  category: ExpenseCategory;
  // Decimal fields are serialized as strings by the API.
  amount: string;
  currency: string;
  converted_amount: string | null;
  converted_currency: string | null;
  exchange_rate: string | null;
  exchange_rate_date: string | null;
  occurred_at: string | null;
  description: string | null;
  trip_id: string | null;
  source_type: ExpenseSourceType | null;
  source_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExpenseInput {
  category?: ExpenseCategory;
  amount?: number;
  currency?: string;
  converted_amount?: number | null;
  converted_currency?: string | null;
  exchange_rate?: number | null;
  exchange_rate_date?: string | null;
  occurred_at?: string | null;
  description?: string | null;
  trip_id?: string | null;
  source_type?: ExpenseSourceType | null;
  source_id?: string | null;
}

export interface ExpenseFilters {
  search?: string;
  category?: ExpenseCategory;
  trip_id?: string;
  source_type?: ExpenseSourceType;
  source_id?: string;
  date_from?: string;
  date_to?: string;
  sort?: "newest" | "oldest" | "amount" | "created";
  page?: number;
  page_size?: number;
}

export interface ExpenseCurrencyTotal {
  currency: string;
  amount: string;
}

export interface ExpenseSummary {
  report_currency: string;
  converted_total: string;
  converted_count: number;
  unconverted_count: number;
  unconverted: ExpenseCurrencyTotal[];
}

/** One spend bucket normalised to the report currency. */
export interface ExpenseBreakdownItem {
  label: string;
  name?: string | null;
  amount: string;
  count: number;
  unconverted_count: number;
}

/** Original-currency total plus the portion convertible to the report currency. */
export interface ExpenseCurrencyBreakdown {
  currency: string;
  amount: string;
  count: number;
  converted_amount?: string | null;
  converted_currency?: string | null;
}

export interface ExpenseStatistics {
  report_currency: string;
  total: string;
  count: number;
  converted_count: number;
  unconverted_count: number;
  average: string;
  largest: string;
  by_category: ExpenseBreakdownItem[];
  by_month: ExpenseBreakdownItem[];
  by_year: ExpenseBreakdownItem[];
  by_source_type: ExpenseBreakdownItem[];
  by_trip: ExpenseBreakdownItem[];
  by_currency: ExpenseCurrencyBreakdown[];
  unconverted: ExpenseCurrencyTotal[];
}

export interface ExpenseList {
  items: Expense[];
  total: number;
  page: number;
  page_size: number;
}

export interface Note {
  id: string;
  user_id: string;
  title: string;
  content: string | null;
  trip_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface NoteInput {
  title?: string;
  content?: string | null;
  trip_id?: string | null;
}

export interface NoteFilters {
  search?: string;
  trip_id?: string;
  sort?: "newest" | "oldest" | "updated" | "title";
  page?: number;
  page_size?: number;
}

export interface NoteList {
  items: Note[];
  total: number;
  page: number;
  page_size: number;
}

export type PlaceType =
  | "airport"
  | "train_station"
  | "bus_station"
  | "port"
  | "hotel"
  | "restaurant"
  | "attraction"
  | "city"
  | "place"
  | "other";

export interface Place {
  id: string;
  user_id: string;
  type: PlaceType;
  country: string | null;
  region: string | null;
  city: string | null;
  district: string | null;
  name: string;
  localized_name: string | null;
  lat: number | null;
  lon: number | null;
  timezone: string | null;
  external_ids: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PlaceSummary {
  id: string;
  name: string;
  localized_name: string | null;
  city: string | null;
}

export interface PlaceInput {
  type?: PlaceType;
  country?: string | null;
  region?: string | null;
  city?: string | null;
  district?: string | null;
  name?: string;
  localized_name?: string | null;
  lat?: number | null;
  lon?: number | null;
  timezone?: string | null;
  external_ids?: Record<string, unknown> | null;
}

export interface PlaceFilters {
  search?: string;
  type?: PlaceType;
  page?: number;
  page_size?: number;
}

export interface PlaceList {
  items: Place[];
  total: number;
  page: number;
  page_size: number;
}

export type ActivityType =
  | "sightseeing"
  | "theme_park"
  | "museum"
  | "culture"
  | "outdoor"
  | "sports"
  | "dining"
  | "shopping"
  | "entertainment"
  | "event"
  | "experience"
  | "wellness"
  | "visit"
  | "other";

export interface Activity {
  id: string;
  user_id: string;
  name: string;
  type: ActivityType;
  place_id: string | null;
  place: PlaceSummary | null;
  start_at: string | null;
  end_at: string | null;
  timezone: string | null;
  // Decimal fields are serialized as strings by the API.
  price: string | null;
  currency: string | null;
  notes: string | null;
  trip_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActivityInput {
  name?: string;
  type?: ActivityType;
  place_id?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  timezone?: string | null;
  price?: number | null;
  currency?: string | null;
  notes?: string | null;
  trip_id?: string | null;
}

export interface ActivityFilters {
  search?: string;
  type?: ActivityType;
  trip_id?: string;
  place_id?: string;
  sort?: "newest" | "oldest" | "created";
  page?: number;
  page_size?: number;
}

export interface ActivityList {
  items: Activity[];
  total: number;
  page: number;
  page_size: number;
}

export interface TripItemCreate {
  item_type: "place";
  item_id: string;
  start_at?: string | null;
  end_at?: string | null;
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

export type TimelineOrderMode = "chronological" | "manual";

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
  timeline_order_mode: TimelineOrderMode;
  created_at: string;
  updated_at: string;
}

export interface TripInput {
  name?: string;
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  cover_image?: string | null;
  origin?: string | null;
  destination?: string | null;
  status?: string;
  timeline_order_mode?: TimelineOrderMode;
}

export interface TripItem {
  // Null only when the source record has no projection yet; run the explicit
  // timeline repair endpoint before reordering.
  id: string | null;
  item_type: string;
  item_id: string;
  sort_order: number;
  time_kind: "instant" | "date";
  start_at: string | null;
  end_at: string | null;
  start_date: string | null;
  end_date: string | null;
  timezone: string | null;
  is_unscheduled: boolean;
  record: TimelineRecord | null;
  hotel: Hotel | null;
  activity: Activity | null;
}

export interface TripDetail extends Trip {
  records: TimelineRecord[];
  items: TripItem[];
  expenses: Expense[];
  expense_summary: ExpenseSummary | null;
  notes: Note[];
  attachments: Attachment[];
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
  /** Raw client address as seen by the server (authorised for traceability). */
  ip: string | null;
  /** Salted hash of the client IP — stable pseudonymous key. */
  ip_hash: string | null;
  /** Sanitised client hint. */
  user_agent: string | null;
  /** Opaque id correlating every audit row one request produced. */
  request_id: string | null;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface DataSource {
  id: string;
  source_type: string;
  source_name: string;
  source_url: string | null;
  retrieved_at: string;
  confidence: number | null;
  provider: string | null;
  metadata: Record<string, unknown> | null;
}

export interface DataSourceList {
  items: DataSource[];
  total: number;
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

export interface AdminSettings {
  allow_registration: boolean;
  registration_captcha_enabled: boolean;
  captcha_provider: "arithmetic" | "turnstile";
  turnstile_site_key: string | null;
  turnstile_secret_set: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_sender: string | null;
  smtp_starttls: boolean;
  smtp_password_set: boolean;
}

export interface AdminSettingsUpdateInput {
  allow_registration?: boolean;
  registration_captcha_enabled?: boolean;
  captcha_provider?: "arithmetic" | "turnstile";
  turnstile_site_key?: string;
  turnstile_secret?: string;
  smtp_host?: string;
  smtp_port?: number | null;
  smtp_username?: string;
  smtp_password?: string;
  smtp_sender?: string;
  smtp_starttls?: boolean;
}

export interface AdminUserCreateInput {
  username: string;
  password: string;
  email?: string;
  display_name?: string;
  role?: "USER" | "ADMIN";
}

export interface AuthConfig {
  allow_registration: boolean;
  registration_captcha_enabled: boolean;
  captcha_provider: "arithmetic" | "turnstile";
  turnstile_site_key: string | null;
}

export interface CaptchaChallenge {
  token: string;
  question: string;
}

export interface AdminAuditLog {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  meta: Record<string, unknown> | null;
  /** Raw client address as seen by the server (authorised for traceability). */
  ip: string | null;
  /** Salted hash of the client IP — stable pseudonymous key. */
  ip_hash: string | null;
  /** Sanitised client hint. */
  user_agent: string | null;
  /** Opaque id correlating every audit row one request produced. */
  request_id: string | null;
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

export type AccessTokenScope = "read" | "write";

export interface AccessToken {
  id: string;
  name: string;
  token_prefix: string;
  scope: AccessTokenScope;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface AccessTokenCreated extends AccessToken {
  token: string;
}

export interface AccessTokenList {
  items: AccessToken[];
}

export type PendingActionStatus = "pending" | "confirmed" | "rejected" | "failed" | "expired";

export interface PendingAction {
  id: string;
  action: "create" | "update";
  record_type:
    | "flight"
    | "train"
    | "other"
    | "hotel"
    | "trip"
    | "expense"
    | "note"
    | "place"
    | "activity";
  summary: string;
  payload: Record<string, unknown>;
  status: PendingActionStatus;
  result: { record_type: string; record_id: string } | null;
  error: string | null;
  token_name: string | null;
  created_at: string;
  expires_at: string | null;
  resolved_at: string | null;
}

export interface PendingActionList {
  items: PendingAction[];
  total: number;
  page: number;
  page_size: number;
  pending_total: number;
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
  hotels: number;
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
  departure_timezone: string | null;
  arrival_timezone: string | null;
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
  hotels: number;
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
  expense_summary: ExpenseSummary;
  expense_stats: ExpenseStatistics;
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
  hotels: MapHotel[];
  places: MapPlace[];
}

export interface MapPlace {
  id: string;
  name: string;
  type: PlaceType;
  lat: number;
  lon: number;
  city: string | null;
}

export interface MapHotel {
  id: string;
  name: string;
  lat: number;
  lon: number;
  check_in: string;
  check_out: string | null;
  status: string;
}

export interface WrappedTotals {
  countries: number;
  cities: number;
  distance_km: number;
  trips: number;
  flights: number;
  trains: number;
  transports: number;
  hotels: number;
  hotel_nights: number;
  activities: number;
  travel_days: number;
}

export interface WrappedRoute {
  id: string;
  type: string;
  service_number: string | null;
  carrier: string | null;
  origin: MapPoint;
  destination: MapPoint;
  distance_km: number;
  departure_date: string | null;
}

export interface WrappedRead {
  year: number;
  available_years: number[];
  totals: WrappedTotals;
  by_month: BreakdownItem[];
  top_airlines: BreakdownItem[];
  top_airports: BreakdownItem[];
  top_stations: BreakdownItem[];
  top_aircraft: BreakdownItem[];
  most_visited_city: BreakdownItem | null;
  favorite_trip: BreakdownItem | null;
  longest_route: WrappedRoute | null;
  first_journey: string | null;
  last_journey: string | null;
  spend: ExpenseSummary;
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

export interface AiHistoryProposalOutcome {
  action: string;
  record_type: string;
  summary: string;
  status: "pending" | "saved" | "cancelled" | "duplicate";
}

/** Prior chat turn relayed to the stateless backend for continuity. */
export interface AiHistoryMessage {
  role: "user" | "assistant";
  content: string;
  proposals?: AiHistoryProposalOutcome[];
  reasoning?: string;
}

export interface AiChatResponse {
  reply: string;
  proposals: AiProposal[];
}

export interface AiStreamEvent {
  type: "reasoning" | "text" | "proposals" | "done" | "error";
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
  warnings: string[];
}

export interface ImportResult {
  imported: number;
  skipped_duplicates: number;
  failed: number;
  trips_created: number;
  errors: ImportRowError[];
}

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

export interface TripDetail extends Trip {
  flights: Flight[];
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
  web_search: boolean;
}

export interface AiSettingsWrite {
  provider: string;
  model: string;
  base_url?: string | null;
  api_key?: string | null;
  temperature?: number | null;
  context_limit?: number | null;
  web_search?: boolean;
}

export interface DashboardStats {
  countries: number;
  cities: number;
  journeys: number;
  distance_km: number;
  flights: number;
  trains: number;
  trips: number;
}

export interface DashboardRead {
  stats: DashboardStats;
  recent: Flight[];
  upcoming: Flight | null;
}

export interface BreakdownItem {
  label: string;
  name: string | null;
  count: number;
}

export interface StatisticsRead {
  by_month: BreakdownItem[];
  by_airline: BreakdownItem[];
  by_alliance: BreakdownItem[];
  by_airport: BreakdownItem[];
  by_aircraft: BreakdownItem[];
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

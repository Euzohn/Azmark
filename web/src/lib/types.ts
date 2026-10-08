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
  departure_timezone: string | null;
  arrival_timezone: string | null;
  origin: string | null;
  destination: string | null;
  carrier: string | null;
  service_number: string | null;
  seat: string | null;
  terminal: string | null;
  gate: string | null;
  booking_reference: string | null;
  ticket_number: string | null;
  price: string | null;
  currency: string | null;
  notes: string | null;
  trip_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlightInput {
  status?: string;
  departure_time?: string | null;
  arrival_time?: string | null;
  departure_timezone?: string | null;
  arrival_timezone?: string | null;
  origin?: string | null;
  destination?: string | null;
  carrier?: string | null;
  service_number?: string | null;
  seat?: string | null;
  terminal?: string | null;
  gate?: string | null;
  booking_reference?: string | null;
  ticket_number?: string | null;
  price?: string | null;
  currency?: string | null;
  notes?: string | null;
}

export interface FlightList {
  items: Flight[];
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
  city: string | null;
  country: string | null;
  lat: number | null;
  lon: number | null;
}

export interface Airline {
  iata: string;
  icao: string | null;
  name: string;
  country: string | null;
}

export interface FlightNumberLookup {
  flight_number: string;
  airline_code: string | null;
  airline: Airline | null;
}

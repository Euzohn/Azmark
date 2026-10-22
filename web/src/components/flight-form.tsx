"use client";

import { useQuery } from "@tanstack/react-query";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";

import { Columns2, Loader2, Wand2 } from "lucide-react";
import Link from "next/link";

import { AllianceBadge } from "@/components/alliance-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Combobox } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { fromZonedInput, toZonedInput, todayInZone } from "@/lib/datetime";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { defaultTimezone } from "@/lib/timezones";
import { useFormDiff } from "@/lib/use-form-diff";
import { cn } from "@/lib/utils";
import type { Flight, FlightInput, FlightLookup, ProviderLookupResult } from "@/lib/types";

function timePart(value: string): string {
  return value.includes("T") ? value.slice(11, 16) : "";
}

function datePart(value: string): string {
  return value.slice(0, 10);
}

function joinDateTime(date: string, time: string): string {
  if (!date) return "";
  return time ? `${date}T${time}` : date;
}

// 航班日期已过 → 默认「已完成」，否则「计划中」。空/非法返回 null 表示不干预。
// `tz` is the record's IANA timezone; the naive `departure` wall-clock is read
// in that zone so the comparison is correct across timezones.
function autoStatus(departure: string, tz: string): string | null {
  if (!departure) return null;
  const iso = fromZonedInput(departure, tz);
  if (!iso) return null;
  return new Date(iso).getTime() < Date.now() ? "completed" : "scheduled";
}

// 只有日期时按日历日比较：今天及以后仍是「计划中」，避免把今天晚些的航班误判为已完成。
function autoStatusByDate(value: string, tz: string): string | null {
  const date = value.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  return date < todayInZone(tz) ? "completed" : "scheduled";
}

// Display an ISO instant as a wall-clock in the record's timezone.
function formatDateTime(value: string | null | undefined, tz?: string | null): string {
  if (!value) return "";
  const zoned = toZonedInput(value, tz);
  return zoned ? zoned.replace("T", " ") : "";
}

function providerLabel(name: string): string {
  if (name === "aerodatabox") return "AeroDataBox";
  if (name === "aviationstack") return "AviationStack";
  if (name === "variflight") return "VariFlight";
  return name;
}

const SCHEDULE_KEYS = [
  "departure_time",
  "arrival_time",
  "actual_departure_time",
  "actual_arrival_time",
] as const;

type FlightFormState = {
  service_number: string;
  carrier: string;
  airline_code: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  actual_departure_time: string;
  actual_arrival_time: string;
  seat: string;
  seat_type: string;
  cabin_class: string;
  departure_terminal: string;
  departure_gate: string;
  arrival_terminal: string;
  arrival_gate: string;
  check_in_desk: string;
  baggage_belt: string;
  aircraft_model: string;
  aircraft_reg: string;
  departure_timezone: string;
  arrival_timezone: string;
  status: string;
  price: string;
  currency: string;
  distance: string;
  ticket_number: string;
  booking_reference: string;
  purchase_credential_type: string;
  purchase_credential: string;
  notes: string;
  trip_id: string;
};

/** The value each field would hold if untouched: the saved record, or blank. */
function snapshot(initial?: Flight): FlightFormState {
  return {
    service_number: initial?.service_number ?? "",
    carrier: initial?.carrier ?? "",
    airline_code: initial?.airline_code ?? "",
    origin: initial?.origin ?? "",
    destination: initial?.destination ?? "",
    departure_time: toZonedInput(initial?.departure_time, initial?.departure_timezone),
    arrival_time: toZonedInput(initial?.arrival_time, initial?.arrival_timezone),
    actual_departure_time: toZonedInput(
      initial?.actual_departure_time,
      initial?.departure_timezone,
    ),
    actual_arrival_time: toZonedInput(
      initial?.actual_arrival_time,
      initial?.arrival_timezone,
    ),
    seat: initial?.seat ?? "",
    seat_type: initial?.seat_type ?? "",
    cabin_class: initial?.cabin_class ?? "",
    departure_terminal: initial?.departure_terminal ?? "",
    departure_gate: initial?.departure_gate ?? "",
    arrival_terminal: initial?.arrival_terminal ?? "",
    arrival_gate: initial?.arrival_gate ?? "",
    check_in_desk: initial?.check_in_desk ?? "",
    baggage_belt: initial?.baggage_belt ?? "",
    aircraft_model: initial?.aircraft_model ?? "",
    aircraft_reg: initial?.aircraft_reg ?? "",
    departure_timezone: initial?.departure_timezone ?? "",
    arrival_timezone: initial?.arrival_timezone ?? "",
    status: initial?.status ?? "scheduled",
    price: initial?.price ?? "",
    currency: initial?.currency ?? "CNY",
    distance: initial?.distance ?? "",
    ticket_number: initial?.ticket_number ?? "",
    booking_reference: initial?.booking_reference ?? "",
    purchase_credential_type: initial?.purchase_credential_type ?? "",
    purchase_credential: initial?.purchase_credential ?? "",
    notes: initial?.notes ?? "",
    trip_id: initial?.trip_id ?? "",
  };
}

const FIELD_LABELS: Record<keyof FlightFormState, TranslationKey> = {
  service_number: "flights.serviceNumber",
  carrier: "flights.carrier",
  airline_code: "flights.carrier",
  origin: "flights.origin",
  destination: "flights.destination",
  departure_time: "flights.departureTime",
  arrival_time: "flights.arrivalTime",
  actual_departure_time: "flights.actualDepartureTime",
  actual_arrival_time: "flights.actualArrivalTime",
  seat: "flights.seat",
  seat_type: "flights.seatType",
  cabin_class: "flights.cabinClass",
  departure_terminal: "flights.departureTerminal",
  departure_gate: "flights.departureGate",
  arrival_terminal: "flights.arrivalTerminal",
  arrival_gate: "flights.arrivalGate",
  check_in_desk: "flights.checkInDesk",
  baggage_belt: "flights.baggageBelt",
  aircraft_model: "flights.aircraftModel",
  aircraft_reg: "flights.aircraftReg",
  departure_timezone: "flights.departureTimezone",
  arrival_timezone: "flights.arrivalTimezone",
  status: "flights.status",
  price: "flights.price",
  currency: "flights.currency",
  distance: "flights.distance",
  ticket_number: "flights.ticketNumber",
  booking_reference: "flights.bookingReference",
  purchase_credential_type: "flights.purchaseCredentialType",
  purchase_credential: "flights.purchaseCredential",
  notes: "flights.notes",
  trip_id: "flights.trip",
};

interface FlightFormProps {
  initial?: Flight;
  submitting?: boolean;
  onSubmit: (data: FlightInput) => void | Promise<void>;
}

export function FlightForm({ initial, submitting, onSubmit }: FlightFormProps) {
  const { user } = useAuth();
  const { t, locale } = useI18n();
  const [form, setForm] = useState<FlightFormState>(() => {
    const base = snapshot(initial);
    if (initial) return base;
    // A new record starts in the traveller's own zone (profile setting); a
    // provider lookup or a manual pick still wins.
    const tz = defaultTimezone(user?.timezone);
    return {
      ...base,
      departure_timezone: base.departure_timezone || tz,
      arrival_timezone: base.arrival_timezone || tz,
    };
  });

  const { data: trips } = useQuery({
    queryKey: ["trips"],
    queryFn: () => api.listTrips(),
  });

  const { data: providerKeys } = useQuery({
    queryKey: ["provider-keys"],
    queryFn: api.listProviderKeys,
  });
  const configuredProviders = (providerKeys?.providers ?? [])
    .filter((item) => item.configured)
    .map((item) => item.provider);
  const canCompare = configuredProviders.length >= 2;

  const [selectedProvider, setSelectedProvider] = useState<string>("auto");
  const [compareStatus, setCompareStatus] = useState<"idle" | "running" | "error">("idle");
  const [compareResults, setCompareResults] = useState<ProviderLookupResult[] | null>(null);

  const [lookupStatus, setLookupStatus] = useState<"idle" | "running" | "ok" | "local" | "error">(
    "idle",
  );
  const [lookupSource, setLookupSource] = useState<string | null>(null);
  const [lookupDate, setLookupDate] = useState(
    initial?.departure_time?.slice(0, 10) || new Date().toISOString().slice(0, 10),
  );
  const [statusTouched, setStatusTouched] = useState(Boolean(initial));
  // Whether the user typed/picked the airline themselves. Provider lookups may
  // correct an auto-inferred (prefix-based) carrier but never a manual edit.
  const [carrierTouched, setCarrierTouched] = useState(Boolean(initial?.carrier));
  // Same rule for timezones: a lookup may move the pre-filled default, but a
  // manual pick is kept.
  const [tzTouched, setTzTouched] = useState(
    Boolean(initial?.departure_timezone || initial?.arrival_timezone),
  );
  const [lastVerified, setLastVerified] = useState<string | null>(null);

  const set = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const editing = Boolean(initial);
  const baseline = useMemo(() => snapshot(initial), [initial]);
  const { changed, changedLabels } = useFormDiff(form, baseline, FIELD_LABELS);
  const joiner = locale === "zh-CN" ? "、" : ", ";
  // Mark only when editing — a blank record is not "modified".
  const isChanged = (key: keyof FlightFormState) => editing && changed.has(key);
  // The carrier name and its IATA code are one logical pick; mark the carrier
  // field if either moved.
  const carrierChanged = editing && (changed.has("carrier") || changed.has("airline_code"));
  // The two share a label, so a name+code change collapses into one summary row.
  const summaryLabels = [...new Set(changedLabels)];

  // 航班日期是锚点：把已填写的时刻平移到这一天（时间不变），空字段由日期输入框继承。
  const changeLookupDate = (date: string) => {
    setLookupDate(date);
    if (!date) return;
    setForm((prev) => {
      const next = { ...prev };
      for (const key of SCHEDULE_KEYS) {
        if (prev[key]) next[key] = joinDateTime(date, timePart(prev[key]));
      }
      if (!statusTouched) {
        const status = autoStatusByDate(date, prev.departure_timezone);
        if (status) next.status = status;
      }
      return next;
    });
  };

  // 变更起飞时间时同步推断状态（用户手动改过状态则不覆盖）。
  const setDepartureTime = (value: string) => {
    if (value) changeLookupDate(datePart(value));
    setForm((prev) => {
      const next = { ...prev, departure_time: value };
      if (!statusTouched) {
        const status = value.includes("T")
          ? autoStatus(value, prev.departure_timezone)
          : autoStatusByDate(value, prev.departure_timezone);
        if (status) next.status = status;
      }
      return next;
    });
  };

  const fetchAirports = useCallback(
    async (query: string) => {
      const airports = await api.searchAirports(query);
      return airports.map((airport) => {
        const name = locale === "zh-CN" ? (airport.name_zh ?? airport.name) : airport.name;
        const city = locale === "zh-CN" ? (airport.city_zh ?? airport.city) : airport.city;
        return {
          value: airport.iata,
          label: `${airport.iata} · ${name}`,
          hint: [city, airport.country].filter(Boolean).join(", ") || undefined,
        };
      });
    },
    [locale],
  );

  const fetchAirlines = useCallback(
    async (query: string) => {
      const airlines = await api.searchAirlines(query);
      return airlines.map((airline) => {
        const name = locale === "zh-CN" ? (airline.name_zh ?? airline.name) : airline.name;
        return {
          value: name,
          label: `${airline.iata} · ${name}`,
          hint: airline.country ?? undefined,
          data: { iata: airline.iata },
        };
      });
    },
    [locale],
  );

  // Infer the airline from the flight-number prefix (spec #38, local-only).
  useEffect(() => {
    const value = form.service_number.trim();
    if (!/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(value) || form.carrier.trim()) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .lookupFlightNumber(value)
        .then((result) => {
          if (cancelled || !result.airline) return;
          const name =
            locale === "zh-CN"
              ? result.airline.name_zh ?? result.airline.name
              : result.airline.name;
          setForm((prev) => (prev.carrier.trim() ? prev : { ...prev, carrier: name }));
        })
        .catch(() => {
          // Lookup is best-effort; the user can always type the airline.
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [form.service_number, form.carrier, locale]);

  const applyLookupResult = useCallback(
    (result: FlightLookup, opts?: { force?: boolean }) => {
      const force = opts?.force ?? false;
      setForm((prev) => {
        const next = { ...prev };
        const airlineName =
          locale === "zh-CN"
            ? (result.airline_name_zh ?? result.airline_name ?? "")
            : result.airline_name ?? "";
        // The provider is authoritative for an auto-inferred carrier; a manual
        // edit is kept unless the user explicitly applies a result (force).
        // This is what lets the flight APIs verify/correct the prefix guess.
        if (airlineName && (force || !carrierTouched || !next.carrier.trim())) {
          next.carrier = airlineName;
        }
        if (result.airline_code && (force || !carrierTouched || !next.airline_code)) {
          next.airline_code = result.airline_code;
        }
        if (result.origin_iata && !next.origin.trim()) next.origin = result.origin_iata;
        if (result.destination_iata && !next.destination.trim())
          next.destination = result.destination_iata;
        if (result.departure_time && !next.departure_time) {
          next.departure_time = toZonedInput(
            result.departure_time,
            result.departure_timezone || next.departure_timezone,
          );
          if (!statusTouched) {
            const status = autoStatus(
              next.departure_time,
              result.departure_timezone || next.departure_timezone,
            );
            if (status) next.status = status;
          }
        }
        if (result.arrival_time && !next.arrival_time)
          next.arrival_time = toZonedInput(
            result.arrival_time,
            result.arrival_timezone || next.arrival_timezone,
          );
        if (result.actual_departure_time && !next.actual_departure_time)
          next.actual_departure_time = toZonedInput(
            result.actual_departure_time,
            result.departure_timezone || next.departure_timezone,
          );
        if (result.actual_arrival_time && !next.actual_arrival_time)
          next.actual_arrival_time = toZonedInput(
            result.actual_arrival_time,
            result.arrival_timezone || next.arrival_timezone,
          );
        if (result.status && !statusTouched) next.status = result.status;
        if (result.departure_terminal && !next.departure_terminal)
          next.departure_terminal = result.departure_terminal;
        if (result.departure_gate && !next.departure_gate)
          next.departure_gate = result.departure_gate;
        if (result.arrival_terminal && !next.arrival_terminal)
          next.arrival_terminal = result.arrival_terminal;
        if (result.arrival_gate && !next.arrival_gate)
          next.arrival_gate = result.arrival_gate;
        if (result.check_in_desk && !next.check_in_desk)
          next.check_in_desk = result.check_in_desk;
        if (result.baggage_belt && !next.baggage_belt)
          next.baggage_belt = result.baggage_belt;
        if (result.aircraft_model && !next.aircraft_model)
          next.aircraft_model = result.aircraft_model;
        if (result.aircraft_reg && !next.aircraft_reg) next.aircraft_reg = result.aircraft_reg;
        if (result.departure_timezone && (force || !tzTouched || !next.departure_timezone))
          next.departure_timezone = result.departure_timezone;
        if (result.arrival_timezone && (force || !tzTouched || !next.arrival_timezone))
          next.arrival_timezone = result.arrival_timezone;
        if (result.distance && !next.distance) next.distance = String(result.distance);
        return next;
      });
      if (result.departure_time) {
        setLookupDate(result.departure_time.slice(0, 10));
      }
      if (result.source && result.source !== "local") {
        setLookupSource(result.source);
        setLookupStatus("ok");
      } else {
        setLookupStatus("local");
      }
    },
    [locale, statusTouched, carrierTouched, tzTouched],
  );

  const runLookup = async (force = false) => {
    const number = form.service_number.trim();
    if (!/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(number)) return;
    setLookupStatus("running");
    const datePart = lookupDate || new Date().toISOString().slice(0, 10);
    try {
      const result = await api.lookupFlight({
        flight_number: number,
        date: datePart,
        provider: selectedProvider === "auto" ? undefined : selectedProvider,
      });
      applyLookupResult(result, { force });
    } catch {
      setLookupStatus("error");
    }
  };

  // With provider keys configured, verify the number against the flight APIs
  // once the user leaves the field (one request per distinct number). The
  // local prefix guess is instant; this confirms/corrects it.
  const verifyOnBlur = () => {
    const number = form.service_number.trim();
    if (!/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(number)) return;
    if (!configuredProviders.length) return;
    if (lookupStatus === "running" || lastVerified === number) return;
    setLastVerified(number);
    void runLookup(false);
  };

  const runCompare = async () => {
    const number = form.service_number.trim();
    if (!canCompare || !/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(number)) return;
    setCompareStatus("running");
    setCompareResults(null);
    const datePart = lookupDate || new Date().toISOString().slice(0, 10);
    try {
      const data = await api.lookupFlightAll({ flight_number: number, date: datePart });
      setCompareResults(data.results);
      setCompareStatus("idle");
    } catch {
      setCompareStatus("error");
    }
  };

  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!form.origin.trim() || !form.destination.trim()) {
      setFormError(t("flights.requiredRoute"));
      return;
    }
    const data: FlightInput = {
      service_number: form.service_number || null,
      carrier: form.carrier || null,
      airline_code: form.airline_code || null,
      origin: form.origin || null,
      destination: form.destination || null,
      departure_time: fromZonedInput(form.departure_time, form.departure_timezone),
      arrival_time: fromZonedInput(form.arrival_time, form.arrival_timezone),
      actual_departure_time: fromZonedInput(
        form.actual_departure_time,
        form.departure_timezone,
      ),
      actual_arrival_time: fromZonedInput(
        form.actual_arrival_time,
        form.arrival_timezone,
      ),
      seat: form.seat || null,
      seat_type: form.seat_type || null,
      cabin_class: form.cabin_class || null,
      departure_terminal: form.departure_terminal || null,
      departure_gate: form.departure_gate || null,
      arrival_terminal: form.arrival_terminal || null,
      arrival_gate: form.arrival_gate || null,
      check_in_desk: form.check_in_desk || null,
      baggage_belt: form.baggage_belt || null,
      aircraft_model: form.aircraft_model || null,
      aircraft_reg: form.aircraft_reg || null,
      departure_timezone: form.departure_timezone || null,
      arrival_timezone: form.arrival_timezone || null,
      status: form.status,
      price: form.price || null,
      currency: form.currency || null,
      distance: form.distance || null,
      ticket_number: form.ticket_number || null,
      booking_reference: form.booking_reference || null,
      purchase_credential_type: form.purchase_credential_type || null,
      purchase_credential: form.purchase_credential || null,
      notes: form.notes || null,
      trip_id: form.trip_id || null,
    };
    void onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-8">
      <Section title={t("flights.section.flight")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("flights.serviceNumber")} marked={isChanged("service_number")}>
            <div className="flex gap-2">
              <Input
                value={form.service_number}
                onChange={(e) => set("service_number", e.target.value)}
                onBlur={verifyOnBlur}
                placeholder="CX659"
                className="flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => void runLookup(true)}
                disabled={
                  lookupStatus === "running" ||
                  !/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(form.service_number.trim())
                }
                title={t("flights.lookup")}
                aria-label={t("flights.lookup")}
              >
                {lookupStatus === "running" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Wand2 className="h-4 w-4" />
                )}
              </Button>
              {canCompare ? (
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => void runCompare()}
                  disabled={
                    compareStatus === "running" ||
                    !/^[A-Za-z0-9]{2,3}\d{1,4}$/.test(form.service_number.trim())
                  }
                  title={t("flights.compare")}
                  aria-label={t("flights.compare")}
                >
                  {compareStatus === "running" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Columns2 className="h-4 w-4" />
                  )}
                </Button>
              ) : null}
            </div>
            {lookupStatus !== "idle" ? (
              <p className="mt-1.5 text-xs text-muted-foreground">
                {lookupStatus === "running" ? t("flights.lookupRunning") : null}
                {lookupStatus === "ok"
                  ? t("flights.lookupRemote", { source: lookupSource ?? "" })
                  : null}
                {lookupStatus === "local" ? (
                  <>
                    {t("flights.lookupLocal")}{" "}
                    <Link href="/settings" className="text-primary hover:underline">
                      {t("nav.settings")}
                    </Link>
                  </>
                ) : null}
                {lookupStatus === "error" ? t("flights.lookupFailed") : null}
              </p>
            ) : null}
          </Field>
          <Field label={t("flights.lookupDate")}>
            <Input
              type="date"
              value={lookupDate}
              onChange={(e) => changeLookupDate(e.target.value)}
            />
          </Field>
          {canCompare ? (
            <Field label={t("flights.lookupProvider")}>
              <Select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
              >
                <option value="auto">{t("flights.providerAuto")}</option>
                {configuredProviders.map((name) => (
                  <option key={name} value={name}>
                    {providerLabel(name)}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}
          <Field label={t("flights.carrier")} marked={carrierChanged}>
            <Combobox
              value={form.carrier}
              onChange={(value) => {
                setCarrierTouched(true);
                set("carrier", value);
              }}
              onSelect={(option) => {
                setCarrierTouched(true);
                const iata = option.data?.iata;
                if (iata) set("airline_code", iata);
              }}
              fetchOptions={fetchAirlines}
              placeholder={t("flights.airlineSearch")}
              emptyText={t("flights.noResults")}
            />
            {form.airline_code ? (
              <div className="mt-1.5">
                <AllianceBadge code={form.airline_code} />
              </div>
            ) : null}
          </Field>
          <Field label={t("flights.origin")} required marked={isChanged("origin")}>
            <Combobox
              value={form.origin}
              onChange={(value) => set("origin", value)}
              fetchOptions={fetchAirports}
              placeholder={t("flights.airportSearch")}
              emptyText={t("flights.noResults")}
            />
          </Field>
          <Field label={t("flights.destination")} required marked={isChanged("destination")}>
            <Combobox
              value={form.destination}
              onChange={(value) => set("destination", value)}
              fetchOptions={fetchAirports}
              placeholder={t("flights.airportSearch")}
              emptyText={t("flights.noResults")}
            />
          </Field>
          <Field label={t("flights.trip")} marked={isChanged("trip_id")}>
            <Select value={form.trip_id} onChange={(e) => set("trip_id", e.target.value)}>
              <option value="">{t("flights.tripNone")}</option>
              {trips?.items.map((trip) => (
                <option key={trip.id} value={trip.id}>
                  {trip.name || `${trip.origin ?? ""} → ${trip.destination ?? ""}`}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("flights.status")} marked={isChanged("status")}>
            <Select
              value={form.status}
              onChange={(e) => {
                setStatusTouched(true);
                set("status", e.target.value);
              }}
            >
              <option value="scheduled">{t("flights.status.scheduled")}</option>
              <option value="completed">{t("flights.status.completed")}</option>
              <option value="cancelled">{t("flights.status.cancelled")}</option>
            </Select>
          </Field>
        </div>
        {compareStatus === "error" ? (
          <p className="text-xs text-danger">{t("flights.compareFailed")}</p>
        ) : null}
        {compareResults && compareResults.length > 0 ? (
          <ComparePanel
            results={compareResults}
            onUse={(data) => {
              applyLookupResult(data, { force: true });
              setCompareResults(null);
            }}
            onClose={() => setCompareResults(null)}
          />
        ) : null}
      </Section>

      <Section title={t("flights.section.schedule")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("flights.departureTime")} marked={isChanged("departure_time")}>
            <ScheduleInput
              value={form.departure_time}
              fallbackDate={lookupDate}
              onChange={setDepartureTime}
            />
          </Field>
          <Field label={t("flights.arrivalTime")} marked={isChanged("arrival_time")}>
            <ScheduleInput
              value={form.arrival_time}
              fallbackDate={lookupDate}
              onChange={(value) => set("arrival_time", value)}
            />
          </Field>
          <Field label={t("flights.actualDepartureTime")} marked={isChanged("actual_departure_time")}>
            <ScheduleInput
              value={form.actual_departure_time}
              fallbackDate={lookupDate}
              onChange={(value) => set("actual_departure_time", value)}
            />
          </Field>
          <Field label={t("flights.actualArrivalTime")} marked={isChanged("actual_arrival_time")}>
            <ScheduleInput
              value={form.actual_arrival_time}
              fallbackDate={lookupDate}
              onChange={(value) => set("actual_arrival_time", value)}
            />
          </Field>
          <Field
            label={t("flights.departureTimezone")}
            marked={isChanged("departure_timezone")}
          >
            <TimezoneSelect
              value={form.departure_timezone}
              onChange={(value) => {
                setTzTouched(true);
                set("departure_timezone", value);
              }}
            />
          </Field>
          <Field label={t("flights.arrivalTimezone")} marked={isChanged("arrival_timezone")}>
            <TimezoneSelect
              value={form.arrival_timezone}
              onChange={(value) => {
                setTzTouched(true);
                set("arrival_timezone", value);
              }}
            />
          </Field>
        </div>
      </Section>

      <Section title={t("flights.section.airport")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("flights.departureTerminal")} marked={isChanged("departure_terminal")}>
            <Input
              value={form.departure_terminal}
              onChange={(e) => set("departure_terminal", e.target.value)}
              placeholder="T1"
            />
          </Field>
          <Field label={t("flights.departureGate")} marked={isChanged("departure_gate")}>
            <Input
              value={form.departure_gate}
              onChange={(e) => set("departure_gate", e.target.value)}
              placeholder="23"
            />
          </Field>
          <Field label={t("flights.arrivalTerminal")} marked={isChanged("arrival_terminal")}>
            <Input
              value={form.arrival_terminal}
              onChange={(e) => set("arrival_terminal", e.target.value)}
              placeholder="T4"
            />
          </Field>
          <Field label={t("flights.arrivalGate")} marked={isChanged("arrival_gate")}>
            <Input
              value={form.arrival_gate}
              onChange={(e) => set("arrival_gate", e.target.value)}
              placeholder="B12"
            />
          </Field>
          <Field label={t("flights.checkInDesk")} marked={isChanged("check_in_desk")}>
            <Input
              value={form.check_in_desk}
              onChange={(e) => set("check_in_desk", e.target.value)}
              placeholder="C"
            />
          </Field>
          <Field label={t("flights.baggageBelt")} marked={isChanged("baggage_belt")}>
            <Input
              value={form.baggage_belt}
              onChange={(e) => set("baggage_belt", e.target.value)}
              placeholder="2"
            />
          </Field>
        </div>
      </Section>

      <Section title={t("flights.section.aircraft")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("flights.aircraftModel")} marked={isChanged("aircraft_model")}>
            <Input
              value={form.aircraft_model}
              onChange={(e) => set("aircraft_model", e.target.value)}
              placeholder="Airbus A330-300"
            />
          </Field>
          <Field label={t("flights.aircraftReg")} marked={isChanged("aircraft_reg")}>
            <Input
              value={form.aircraft_reg}
              onChange={(e) => set("aircraft_reg", e.target.value)}
              placeholder="B-HWM"
            />
          </Field>
          <Field label={t("flights.cabinClass")} marked={isChanged("cabin_class")}>
            <Select
              value={form.cabin_class}
              onChange={(e) => set("cabin_class", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="economy">{t("flights.cabin.economy")}</option>
              <option value="premium_economy">{t("flights.cabin.premium_economy")}</option>
              <option value="business">{t("flights.cabin.business")}</option>
              <option value="first">{t("flights.cabin.first")}</option>
            </Select>
          </Field>
          <Field label={t("flights.seatType")} marked={isChanged("seat_type")}>
            <Select
              value={form.seat_type}
              onChange={(e) => set("seat_type", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="window">{t("flights.seatType.window")}</option>
              <option value="aisle">{t("flights.seatType.aisle")}</option>
              <option value="middle">{t("flights.seatType.middle")}</option>
            </Select>
          </Field>
          <Field label={t("flights.seat")} marked={isChanged("seat")}>
            <Input value={form.seat} onChange={(e) => set("seat", e.target.value)} placeholder="32A" />
          </Field>
        </div>
      </Section>

      <Section title={t("flights.section.ticket")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("flights.price")} marked={isChanged("price")}>
            <Input
              type="number"
              step="0.01"
              value={form.price}
              onChange={(e) => set("price", e.target.value)}
            />
          </Field>
          <Field label={t("flights.currency")} marked={isChanged("currency")}>
            <Input
              value={form.currency}
              maxLength={3}
              onChange={(e) => set("currency", e.target.value.toUpperCase())}
            />
          </Field>
          <Field label={t("flights.distance")} marked={isChanged("distance")}>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={form.distance}
              onChange={(e) => set("distance", e.target.value)}
            />
          </Field>
          <Field label={t("flights.ticketNumber")} marked={isChanged("ticket_number")}>
            <Input
              value={form.ticket_number}
              onChange={(e) => set("ticket_number", e.target.value)}
              placeholder="160-1234567890"
            />
          </Field>
          <Field label={t("flights.purchaseCredentialType")} marked={isChanged("purchase_credential_type")}>
            <Select
              value={form.purchase_credential_type}
              onChange={(e) => set("purchase_credential_type", e.target.value)}
            >
              <option value="">{t("flights.credentialType.none")}</option>
              <option value="id_card">{t("flights.credentialType.id_card")}</option>
              <option value="passport">{t("flights.credentialType.passport")}</option>
              <option value="hk_macau_permit">{t("flights.credentialType.hk_macau_permit")}</option>
              <option value="taiwan_permit">{t("flights.credentialType.taiwan_permit")}</option>
              <option value="other">{t("flights.credentialType.other")}</option>
            </Select>
          </Field>
          <Field label={t("flights.purchaseCredential")} marked={isChanged("purchase_credential")}>
            <Input
              value={form.purchase_credential}
              onChange={(e) => set("purchase_credential", e.target.value)}
              placeholder="E12345678"
            />
          </Field>
          <Field
            label={t("flights.bookingReference")}
            marked={isChanged("booking_reference")}
            className="md:col-span-2"
          >
            <Input
              value={form.booking_reference}
              onChange={(e) => set("booking_reference", e.target.value)}
              placeholder="ABCDEF"
              maxLength={6}
            />
          </Field>
        </div>
      </Section>

      <Section title={t("flights.section.notes")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field
            label={t("flights.notes")}
            marked={isChanged("notes")}
            className="md:col-span-2"
          >
            <Textarea
              rows={3}
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
            />
          </Field>
          {editing ? (
            <div className="md:col-span-2">
              {summaryLabels.length > 0 ? (
                <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3.5 py-2.5">
                  <Badge variant="primary">
                    {summaryLabels.length === 1
                      ? t("flights.changedOne")
                      : t("flights.changedMany", { count: summaryLabels.length })}
                  </Badge>
                  <span className="text-sm text-foreground/80">
                    {summaryLabels.join(joiner)}
                  </span>
                </div>
              ) : (
                <p className="px-0.5 text-sm text-muted-foreground">
                  {t("flights.noChanges")}
                </p>
              )}
            </div>
          ) : null}
          <div className="flex items-center gap-3 md:col-span-2">
            <Button type="submit" disabled={submitting}>
              {t("common.save")}
            </Button>
            {formError ? <span className="text-sm text-danger">{formError}</span> : null}
          </div>
        </div>
      </Section>
    </form>
  );
}

function ScheduleInput({
  value,
  fallbackDate,
  onChange,
}: {
  value: string;
  fallbackDate: string;
  onChange: (value: string) => void;
}) {
  const date = datePart(value) || fallbackDate;
  const time = timePart(value);
  return (
    <div className="flex gap-2">
      <Input
        type="date"
        value={date}
        onChange={(e) => onChange(joinDateTime(e.target.value, time))}
        className="flex-1"
      />
      <Input
        type="time"
        value={time}
        onChange={(e) => onChange(joinDateTime(date, e.target.value))}
        className="w-32"
      />
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Field({
  label,
  required,
  marked,
  className,
  children,
}: {
  label: string;
  required?: boolean;
  marked?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className={cn(className, marked && "field-changed")}>
      <Label className="mb-1.5 flex items-center gap-2">
        <span>
          {label}
          {required ? (
            <span className="text-danger" aria-hidden="true">
              *
            </span>
          ) : null}
        </span>
        {marked ? (
          <span className="inline-flex items-center rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-primary">
            {t("flights.changedMarker")}
          </span>
        ) : null}
      </Label>
      {children}
    </div>
  );
}

function ComparePanel({
  results,
  onUse,
  onClose,
}: {
  results: ProviderLookupResult[];
  onUse: (data: FlightLookup) => void;
  onClose: () => void;
}) {
  const { t, locale } = useI18n();

  const rows: { label: string; get: (d: FlightLookup) => string }[] = [
    {
      label: t("flights.carrier"),
      get: (d) =>
        (locale === "zh-CN" ? (d.airline_name_zh ?? d.airline_name) : d.airline_name) ?? "",
    },
    { label: t("flights.origin"), get: (d) => d.origin_iata ?? "" },
    { label: t("flights.destination"), get: (d) => d.destination_iata ?? "" },
    { label: t("flights.departureTime"), get: (d) => formatDateTime(d.departure_time, d.departure_timezone) },
    { label: t("flights.arrivalTime"), get: (d) => formatDateTime(d.arrival_time, d.arrival_timezone) },
    {
      label: t("flights.actualDepartureTime"),
      get: (d) => formatDateTime(d.actual_departure_time, d.departure_timezone),
    },
    { label: t("flights.actualArrivalTime"), get: (d) => formatDateTime(d.actual_arrival_time, d.arrival_timezone) },
    { label: t("flights.departureTerminal"), get: (d) => d.departure_terminal ?? "" },
    { label: t("flights.departureGate"), get: (d) => d.departure_gate ?? "" },
    { label: t("flights.arrivalTerminal"), get: (d) => d.arrival_terminal ?? "" },
    { label: t("flights.arrivalGate"), get: (d) => d.arrival_gate ?? "" },
    { label: t("flights.baggageBelt"), get: (d) => d.baggage_belt ?? "" },
    { label: t("flights.aircraftModel"), get: (d) => d.aircraft_model ?? d.aircraft ?? "" },
    { label: t("flights.distance"), get: (d) => (d.distance ? `${d.distance} km` : "") },
    { label: t("flights.status"), get: (d) => d.status ?? "" },
  ];

  const template = `minmax(7rem, 1fr) repeat(${results.length}, minmax(0, 1fr))`;

  return (
    <Card className="mt-2">
      <CardContent className="p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-medium">{t("flights.compare")}</h3>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            {t("common.cancel")}
          </Button>
        </div>
        <div className="grid gap-x-4 gap-y-1.5 text-sm" style={{ gridTemplateColumns: template }}>
          <div />
          {results.map((item) => (
            <div key={item.provider} className="flex items-center gap-1.5 font-medium">
              {providerLabel(item.provider)}
              {!item.data ? (
                <Badge variant="neutral">{t("flights.compareNoData")}</Badge>
              ) : null}
            </div>
          ))}
          {rows.map((row) => {
            const values = results.map((item) => (item.data ? row.get(item.data) : ""));
            const allEqual = values.every((value) => value === values[0]);
            return (
              <Fragment key={row.label}>
                <div className="text-muted-foreground">{row.label}</div>
                {results.map((item, index) => (
                  <div
                    key={item.provider}
                    className={`break-words ${
                      !allEqual && values[index] ? "font-medium text-primary" : ""
                    }`}
                  >
                    {values[index] || "—"}
                  </div>
                ))}
              </Fragment>
            );
          })}
        </div>
        <div
          className="mt-3 grid gap-x-4"
          style={{ gridTemplateColumns: template }}
        >
          <div />
          {results.map((item) => (
            <Button
              key={item.provider}
              type="button"
              size="sm"
              variant="outline"
              disabled={!item.data}
              onClick={() => item.data && onUse(item.data)}
            >
              {t("flights.compareUse")}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, FileJson, FileSpreadsheet, Upload } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataSourcePanel } from "@/components/data-source-panel";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ImportPreview, ImportResult } from "@/lib/types";

const PREVIEW_COLUMNS = [
  "type",
  "origin",
  "destination",
  "service_number",
  "departure_time",
  "arrival_time",
] as const;

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function formatCell(value: unknown, locale: string): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleString(locale, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  }
  return String(value);
}

export default function DataPage({ embedded = false }: { embedded?: boolean } = {}) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [includeSensitive, setIncludeSensitive] = useState(false);
  const [exporting, setExporting] = useState<"json" | "csv" | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const downloadExport = async (format: "json" | "csv") => {
    setError(null);
    setExporting(format);
    try {
      const blob = await api.exportData(format, includeSensitive);
      saveBlob(blob, `azmark-export.${format}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(null);
    }
  };

  const downloadTemplate = async () => {
    setError(null);
    try {
      saveBlob(await api.importTemplate("csv"), "azmark-import-template.csv");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const previewMutation = useMutation({
    mutationFn: (next: Record<string, string>) => {
      if (!file) throw new Error(t("data.noFile"));
      return api.previewImport(file, next);
    },
    onSuccess: (data) => {
      setPreview(data);
      setMapping(data.field_mapping);
      setResult(null);
      setError(null);
    },
    onError: (err) => setError(err instanceof Error ? err.message : String(err)),
  });

  const importMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error(t("data.noFile"));
      return api.importData(file, mapping);
    },
    onSuccess: (data) => {
      setResult(data);
      setPreview(null);
      setError(null);
      void queryClient.invalidateQueries();
    },
    onError: (err) => setError(err instanceof Error ? err.message : String(err)),
  });

  const chooseFile = (next: File | null) => {
    setFile(next);
    setPreview(null);
    setMapping({});
    setResult(null);
    setError(null);
  };

  const changeMapping = (column: string, target: string) => {
    const next = { ...mapping, [column]: target };
    setMapping(next);
    previewMutation.mutate(next);
  };

  const visibleColumns = PREVIEW_COLUMNS.filter((column) =>
    preview?.rows.some((row) => row[column] !== null && row[column] !== undefined),
  );

  return (
    <div className="flex flex-col gap-6">
      {embedded ? null : (
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight animate-fade-in-up">
            {t("data.title")}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("data.subtitle")}</p>
        </div>
      )}

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      ) : null}

      <Card className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            {t("data.export")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">{t("data.exportHint")}</p>
          <label className="flex items-start gap-3 rounded-lg border border-border p-3">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-[var(--color-primary)]"
              checked={includeSensitive}
              onChange={(event) => setIncludeSensitive(event.target.checked)}
            />
            <span className="flex flex-col gap-1">
              <span className="text-sm font-medium">{t("data.includeSensitive")}</span>
              <span className="text-xs text-muted-foreground">
                {t("data.includeSensitiveHint")}
              </span>
            </span>
          </label>
          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => void downloadExport("json")}
              disabled={exporting !== null}
            >
              <FileJson className="mr-2 h-4 w-4" />
              {t("data.exportJson")}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void downloadExport("csv")}
              disabled={exporting !== null}
            >
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              {t("data.exportCsv")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="animate-fade-in-up" style={{ animationDelay: "100ms" }}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            {t("data.import")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <p className="text-sm text-muted-foreground">{t("data.importHint")}</p>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <Label className="mb-1.5 block" htmlFor="import-file">
                {t("data.chooseFile")}
              </Label>
              <input
                id="import-file"
                type="file"
                accept=".csv,.json,text/csv,application/json"
                className="block w-full cursor-pointer rounded-md border border-border bg-background px-3 py-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:text-foreground"
                onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <Button
              type="button"
              onClick={() => previewMutation.mutate(mapping)}
              disabled={!file || previewMutation.isPending}
            >
              {previewMutation.isPending ? t("data.previewing") : t("data.preview")}
            </Button>
            <Button type="button" variant="ghost" onClick={() => void downloadTemplate()}>
              {t("data.template")}
            </Button>
          </div>

          {preview ? (
            <div className="flex flex-col gap-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="neutral">
                  {t("data.summary", {
                    total: preview.total,
                    valid: preview.valid,
                    duplicates: preview.duplicate_count,
                    errors: preview.error_count,
                  })}
                </Badge>
                {preview.truncated ? (
                  <span className="text-xs text-muted-foreground">
                    {t("data.truncated", { count: preview.rows.length })}
                  </span>
                ) : null}
              </div>

              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-semibold">{t("data.mapping")}</h3>
                <p className="text-xs text-muted-foreground">{t("data.mappingHint")}</p>
                <div className="grid gap-2 md:grid-cols-2">
                  {preview.columns.map((column) => (
                    <div key={column} className="flex items-center gap-2">
                      <span className="w-2/5 truncate font-mono text-xs" title={column}>
                        {column}
                      </span>
                      <select
                        className="h-9 flex-1 rounded-md border border-border bg-background px-2 text-sm"
                        value={mapping[column] ?? ""}
                        onChange={(event) => changeMapping(column, event.target.value)}
                        disabled={previewMutation.isPending}
                      >
                        <option value="">{t("data.ignore")}</option>
                        {preview.target_fields.map((field) => (
                          <option key={field} value={field}>
                            {field}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              {preview.errors.length > 0 ? (
                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold text-danger">{t("data.errors")}</h3>
                  <ul className="flex max-h-48 flex-col gap-1 overflow-auto rounded-lg border border-border p-3 text-xs">
                    {preview.errors.map((item, index) => (
                      <li key={`${item.row}-${index}`} className="text-muted-foreground">
                        <span className="font-medium text-danger">
                          {t("data.row", { row: item.row })}
                        </span>
                        {item.field ? ` · ${item.field}` : ""} · {item.message}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {preview.duplicates.length > 0 ? (
                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold">{t("data.duplicates")}</h3>
                  <p className="text-xs text-muted-foreground">
                    {preview.duplicates
                      .map((item) => t("data.row", { row: item.row }))
                      .join(", ")}
                  </p>
                </div>
              ) : null}

              {preview.rows.length > 0 ? (
                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold">{t("data.rows")}</h3>
                  <div className="overflow-x-auto rounded-lg border border-border">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="px-3 py-2 font-semibold">#</th>
                          {visibleColumns.map((column) => (
                            <th key={column} className="px-3 py-2 font-semibold">
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.rows.map((row, index) => (
                          <tr key={index} className="border-t border-border">
                            <td className="px-3 py-2 text-muted-foreground">{index + 2}</td>
                            {visibleColumns.map((column) => (
                              <td key={column} className="px-3 py-2">
                                {formatCell(row[column], locale)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              <div>
                <Button
                  type="button"
                  onClick={() => importMutation.mutate()}
                  disabled={preview.valid === 0 || importMutation.isPending}
                >
                  {importMutation.isPending ? t("data.importing") : t("data.commit")}
                </Button>
              </div>
            </div>
          ) : null}

          {result ? (
            <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
              {t("data.result", {
                imported: result.imported,
                skipped: result.skipped_duplicates,
                failed: result.failed,
                trips: result.trips_created,
              })}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <DataSourcePanel />
    </div>
  );
}

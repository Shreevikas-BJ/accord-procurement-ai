"use client";
import { useCallback, useEffect, useState } from "react";
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const form = init.body instanceof FormData;
  const response = await fetch("/api" + path, {
    ...init,
    credentials: "same-origin",
    headers: {
      ...(form ? {} : { "Content-Type": "application/json" }),
      "X-Procurement-Client": "workspace",
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "The server could not complete this request." }));
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map(
                (e: { msg: string; loc: string[] }) =>
                  `${e.loc.join(".")}: ${e.msg}`,
              )
              .join("; ")
          : detail?.message || "Request failed. Please retry.",
    );
  }
  return response.json();
}
export function useResource<T>(path: string, poll = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const result = await api<T>(path, { signal: controller.signal });
        setData(result);
        setError("");
      } catch (e) {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Unable to load data.");
      }
    }
    void load();
    const timer = poll ? setInterval(() => void load(), poll) : undefined;
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [path, revision, poll]);
  return { data, error, reload, setData };
}
export function currency(value: unknown, code: string | null = "USD") {
  if (value === null || value === undefined || value === "") return "—";
  if (!code)
    return `${Number(value).toLocaleString("en-US")} (currency missing)`;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: code,
    maximumFractionDigits: 2,
  }).format(Number(value));
}
export function human(value: unknown) {
  return String(value ?? "—")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
export function dateLabel(value: unknown) {
  return value
    ? new Date(String(value).slice(0, 10) + "T12:00:00").toLocaleDateString(
        "en-US",
        { month: "short", day: "numeric", year: "numeric" },
      )
    : "—";
}

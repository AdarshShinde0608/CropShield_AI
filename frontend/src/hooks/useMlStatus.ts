import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { getMlStatus, warmupMlService } from "../api/ml";

let warmupRequested = false;

function errorCode(error: unknown): string | undefined {
  if (!isAxiosError(error)) return undefined;
  const body: unknown = error.response?.data;
  if (typeof body !== "object" || body === null || !("detail" in body)) return undefined;
  const detail = body.detail;
  if (typeof detail === "object" && detail !== null && "code" in detail) {
    return typeof detail.code === "string" ? detail.code : undefined;
  }
  return undefined;
}

export function useMlStatus() {
  const [wakingSince, setWakingSince] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const statusQuery = useQuery({
    queryKey: ["ml-status"],
    queryFn: getMlStatus,
    retry: false,
    refetchInterval: 10_000,
    refetchOnWindowFocus: true
  });
  const code = errorCode(statusQuery.error);
  const waking = statusQuery.isError && code === "ML_WAKING";
  const unavailable = statusQuery.isError && !waking;
  const ready = Boolean(statusQuery.data?.ready ?? statusQuery.data?.status === "ready");

  useEffect(() => {
    if (!warmupRequested) {
      warmupRequested = true;
      void warmupMlService().catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    setWakingSince((started) => waking ? started ?? Date.now() : null);
  }, [waking]);

  useEffect(() => {
    if (!wakingSince) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [wakingSince]);

  const elapsedSeconds = wakingSince ? Math.floor((now - wakingSince) / 1000) : 0;

  return {
    isLoading: statusQuery.isLoading,
    ready,
    waking,
    unavailable,
    errorCode: code,
    secondsRemaining: Math.max(0, 60 - elapsedSeconds)
  };
}

"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useRole } from "@/hooks/useRole";
import { useToast } from "@/components/providers/ToastProvider";
import { apiFetch, API_BASE_URL } from "@/lib/api";
import {
  type ExtensionRequest,
  type Notification,
  type Sandbox,
  type BusinessUnit,
  type PlatformConfiguration,
} from "@/lib/types";

export interface NewRequest {
  businessUnit: string;
  costCenter: string;
  managerEmail: string;
  workload: string;
  region: string;
  role: string;
  description: string;
  justification: string;
  budget: number;
  durationDays: number;
}

interface SandboxContextValue {
  /** The signed-in requestor's own sandboxes. */
  sandboxes: Sandbox[];
  notifications: Notification[];
  /** Every sandbox across all users, for admin screens. */
  adminRequests: Sandbox[];
  extensionRequests: ExtensionRequest[];
  configuration: PlatformConfiguration | null;
  adminBusinessUnits: BusinessUnit[];
  saveBusinessUnit: (unit: Omit<BusinessUnit, "id">, id?: string) => Promise<boolean>;
  importBusinessUnits: (units: unknown) => Promise<boolean>;
  flagCleanup: (id: string, reason: string) => Promise<boolean>;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  addRequest: (req: NewRequest) => Promise<Sandbox | null>;
  requestExtension: (id: string, days: number | null, reason: string, expiryDate?: string) => Promise<boolean>;
  decommissionRequested: (id: string, reason: string) => Promise<boolean>;
  approveRequest: (id: string, budgetOverride?: number) => Promise<boolean>;
  rejectRequest: (id: string, reason: string) => Promise<boolean>;
  retryProvisioning: (id: string) => Promise<boolean>;
  rejectFailed: (id: string, reason: string) => Promise<boolean>;
  approveExtension: (id: string) => Promise<boolean>;
  rejectExtension: (id: string, reason: string) => Promise<boolean>;
  approveDecommission: (id: string) => Promise<boolean>;
  rejectDecommission: (id: string, reason: string) => Promise<boolean>;
}

const SandboxContext = createContext<SandboxContextValue | null>(null);

// Poll quickly while Terraform is running so status changes show up promptly.
const BUSY_POLL_MS = 5_000;
const ADMIN_POLL_MS = 2_000;
const IDLE_POLL_MS = 30_000;

const path = (id: string) => encodeURIComponent(id);

const isBusy = (s: Sandbox) =>
  s.status === "Provisioning" || s.status === "Decommissioning" || !!s.operationInProgress;

export function SandboxProvider({ children }: { children: React.ReactNode }) {
  const { getApiToken } = useAuth();
  const { isAdmin, ready } = useRole();
  const { toast } = useToast();

  const [mine, setMine] = useState<Sandbox[]>([]);
  const [all, setAll] = useState<Sandbox[]>([]);
  const [extensionRequests, setExtensionRequests] = useState<ExtensionRequest[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [configuration, setConfiguration] = useState<PlatformConfiguration | null>(null);
  const [adminBusinessUnits, setAdminBusinessUnits] = useState<BusinessUnit[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // useAuth returns a new getApiToken every render; keep a stable wrapper.
  const tokenRef = useRef(getApiToken);
  useEffect(() => {
    tokenRef.current = getApiToken;
  });
  const getToken = useCallback(() => tokenRef.current(), []);

  const lastError = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [own, every, extensions, notices, config, units] = await Promise.all([
        apiFetch<Sandbox[]>(getToken, "/sandboxes"),
        isAdmin ? apiFetch<Sandbox[]>(getToken, "/admin/sandboxes") : Promise.resolve<Sandbox[]>([]),
        isAdmin
          ? apiFetch<ExtensionRequest[]>(getToken, "/extensions")
          : Promise.resolve<ExtensionRequest[]>([]),
        apiFetch<Notification[]>(getToken, "/notifications"),
        apiFetch<PlatformConfiguration>(getToken, "/configuration"),
        isAdmin ? apiFetch<BusinessUnit[]>(getToken, "/admin/business-units") : Promise.resolve<BusinessUnit[]>([]),
      ]);
      setMine(own);
      setAll(every);
      setExtensionRequests(extensions);
      setNotifications(notices);
      setConfiguration(config);
      setAdminBusinessUnits(units);
      setError(null);
      lastError.current = null;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not load sandboxes.";
      setError(message);
      // Only toast when the error changes, not on every poll.
      if (lastError.current !== message) toast(message, "error");
      lastError.current = message;
    } finally {
      setIsLoading(false);
    }
  }, [getToken, isAdmin, toast]);

  const busy = useMemo(() => mine.some(isBusy) || all.some(isBusy), [mine, all]);

  // Server push: the backend emits "change" when data changes. Polling remains as a fallback.
  const [streamLive, setStreamLive] = useState(false);
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    if (!ready) return;
    let stopped = false;
    let controller: AbortController | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let lastRefresh = 0;
    let pending: ReturnType<typeof setTimeout> | undefined;

    const refresh = () => {
      // Coalesce bursts of changes into at most one refresh per second.
      const wait = Math.max(0, lastRefresh + 1_000 - Date.now());
      if (pending) return;
      pending = setTimeout(() => {
        pending = undefined;
        lastRefresh = Date.now();
        void loadRef.current();
      }, wait);
    };

    const connect = async () => {
      if (stopped) return;
      controller = new AbortController();
      try {
        const token = await getToken();
        if (!token) throw new Error("no token");
        const response = await fetch(`${API_BASE_URL}/api/v1/events`, {
          headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok || !response.body) throw new Error(`stream ${response.status}`);
        setStreamLive(true);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          if (frames.some((frame) => frame.includes("event: change"))) refresh();
        }
      } catch {
        // fall through to reconnect
      }
      setStreamLive(false);
      if (!stopped) reconnect = setTimeout(connect, 3_000);
    };

    void connect();
    return () => {
      stopped = true;
      controller?.abort();
      clearTimeout(reconnect);
      clearTimeout(pending);
      setStreamLive(false);
    };
  }, [ready, getToken]);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    let inFlight = false;
    const tick = async () => {
      // Skip while hidden or while the previous refresh is still running.
      if (cancelled || inFlight || document.hidden) return;
      inFlight = true;
      try {
        await load();
      } finally {
        inFlight = false;
      }
    };
    void tick();
    // With the push stream connected, polling is only a slow safety net.
    const interval = streamLive ? IDLE_POLL_MS : isAdmin ? ADMIN_POLL_MS : busy ? BUSY_POLL_MS : IDLE_POLL_MS;
    const timer = setInterval(tick, interval);
    const onVisible = () => void tick();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [ready, load, busy, isAdmin, streamLive]);

  /** Runs an API action, refreshes data, and toasts any error. */
  const run = useCallback(
    async <T,>(action: () => Promise<T>): Promise<T | null> => {
      try {
        const result = await action();
        await load();
        return result;
      } catch (err) {
        toast(err instanceof Error ? err.message : "Something went wrong.", "error");
        return null;
      }
    },
    [load, toast]
  );

  const post = useCallback(
    <T,>(url: string, body?: unknown) => apiFetch<T>(getToken, url, { method: "POST", body }),
    [getToken]
  );

  const addRequest = useCallback(
    async (req: NewRequest) => run(() => post<Sandbox>("/sandboxes", req)),
    [run, post]
  );

  const requestExtension = useCallback(
    async (id: string, days: number | null, reason: string, expiryDate?: string) => {
      const ext = await run(() =>
        post<ExtensionRequest>(`/sandboxes/${path(id)}/extensions`, expiryDate ? { requestedExpiryDate: expiryDate, reason } : { extraDays: days, reason })
      );
      return ext !== null;
    },
    [run, post]
  );

  const decommissionRequested = useCallback(
    async (id: string, reason: string) => {
      const s = await run(() => post<Sandbox>(`/sandboxes/${path(id)}/decommission`, { reason }));
      return s !== null;
    },
    [run, post]
  );

  const approveRequest = useCallback(
    async (id: string, budgetOverride?: number) =>
      (await run(() => post(`/approvals/${path(id)}/approve`, { budget: budgetOverride }))) !== null,
    [run, post]
  );

  const rejectRequest = useCallback(
    async (id: string, reason: string) => {
      const s = await run(() => post<Sandbox>(`/approvals/${path(id)}/reject`, { reason }));
      return s !== null;
    },
    [run, post]
  );

  const retryProvisioning = useCallback(
    async (id: string) => (await run(() => post(`/admin/sandboxes/${path(id)}/retry`))) !== null,
    [run, post]
  );

  const rejectFailed = useCallback(
    async (id: string, reason: string) =>
      (await run(() => post(`/admin/sandboxes/${path(id)}/reject-failed`, { reason }))) !== null,
    [run, post]
  );

  const approveExtension = useCallback(
    async (id: string) => (await run(() => post(`/extensions/${path(id)}/approve`))) !== null,
    [run, post]
  );

  const rejectExtension = useCallback(
    async (id: string, reason: string) =>
      (await run(() => post(`/extensions/${path(id)}/reject`, { reason }))) !== null,
    [run, post]
  );

  const approveDecommission = useCallback(
    async (id: string) => (await run(() => post(`/decommission/${path(id)}/approve`))) !== null,
    [run, post]
  );

  const rejectDecommission = useCallback(
    async (id: string, reason: string) =>
      (await run(() => post(`/decommission/${path(id)}/reject`, { reason }))) !== null,
    [run, post]
  );

  const saveBusinessUnit = useCallback(
    async (unit: Omit<BusinessUnit, "id">, id?: string) =>
      (await run(() => apiFetch<BusinessUnit>(getToken, `/admin/business-units${id ? `/${path(id)}` : ""}`, { method: id ? "PUT" : "POST", body: unit }))) !== null,
    [run, getToken]
  );

  const flagCleanup = useCallback(
    async (id: string, reason: string) => (await run(() => post(`/admin/sandboxes/${path(id)}/cleanup`, { reason }))) !== null,
    [run, post]
  );

  const importBusinessUnits = useCallback(
    async (units: unknown) => (await run(() => post("/admin/business-units/import", units))) !== null,
    [run, post]
  );

  const value = useMemo(
    () => ({
      sandboxes: mine,
      notifications,
      adminRequests: all,
      extensionRequests,
      configuration,
      adminBusinessUnits,
      saveBusinessUnit,
      importBusinessUnits,
      flagCleanup,
      isLoading,
      error,
      refresh: load,
      addRequest,
      requestExtension,
      decommissionRequested,
      approveRequest,
      rejectRequest,
      retryProvisioning,
      rejectFailed,
      approveExtension,
      rejectExtension,
      approveDecommission,
      rejectDecommission,
    }),
    [
      mine,
      notifications,
      all,
      extensionRequests,
      configuration,
      adminBusinessUnits,
      saveBusinessUnit,
      importBusinessUnits,
      flagCleanup,
      isLoading,
      error,
      load,
      addRequest,
      requestExtension,
      decommissionRequested,
      approveRequest,
      rejectRequest,
      retryProvisioning,
      rejectFailed,
      approveExtension,
      rejectExtension,
      approveDecommission,
      rejectDecommission,
    ]
  );

  return <SandboxContext.Provider value={value}>{children}</SandboxContext.Provider>;
}

export function useSandboxes() {
  const ctx = useContext(SandboxContext);
  if (!ctx) throw new Error("useSandboxes must be used inside SandboxProvider");
  return ctx;
}

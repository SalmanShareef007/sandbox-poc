"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useRole } from "@/hooks/useRole";
import { useToast } from "@/components/providers/ToastProvider";
import { apiFetch } from "@/lib/api";
import {
  DEMO_REQUESTOR_EMAIL,
  notifications as initialNotifications,
  type ExtensionRequest,
  type Notification,
  type Sandbox,
} from "@/lib/demoData";

export interface NewRequest {
  businessUnit: string;
  costCenter: string;
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
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  addRequest: (req: NewRequest) => Promise<Sandbox | null>;
  requestExtension: (id: string, days: ExtensionRequest["extraDays"], reason: string) => Promise<boolean>;
  decommissionRequested: (id: string, reason: string) => Promise<boolean>;
  approveRequest: (id: string, budgetOverride?: number) => Promise<boolean>;
  rejectRequest: (id: string, reason: string) => Promise<boolean>;
  retryProvisioning: (id: string) => Promise<boolean>;
  approveExtension: (id: string) => Promise<boolean>;
  rejectExtension: (id: string, reason: string) => Promise<boolean>;
  approveDecommission: (id: string) => Promise<boolean>;
  rejectDecommission: (id: string, reason: string) => Promise<boolean>;
}

const SandboxContext = createContext<SandboxContextValue | null>(null);

// Poll quickly while Terraform is running so status changes show up promptly.
const BUSY_POLL_MS = 5_000;
const IDLE_POLL_MS = 30_000;

const nowStamp = () => {
  const d = new Date();
  const date = d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  return `${date}, ${time}`;
};

const path = (id: string) => encodeURIComponent(id);

const SPEND_CURVE = [0.06, 0.15, 0.27, 0.39, 0.52, 0.66, 0.83, 1];
const SPENDING: Sandbox["status"][] = ["Active", "Expiring", "Expired", "Decommissioning"];

/**
 * Placeholder spend until Azure Cost Management is integrated (next phase).
 * Deterministic per sandbox so numbers don't jump between refreshes.
 */
function withPlaceholderSpend(s: Sandbox): Sandbox {
  if (!SPENDING.includes(s.status)) return { ...s, spent: 0, spendHistory: undefined };
  let hash = 0;
  for (const ch of s.id) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  const spent = Math.round(s.budget * (0.15 + (hash % 60) / 100) * 100) / 100;
  return { ...s, spent, spendHistory: SPEND_CURVE.map((f) => Math.round(spent * f * 100) / 100) };
}

const isBusy = (s: Sandbox) =>
  s.status === "Provisioning" || s.status === "Decommissioning" || !!s.operationInProgress;

export function SandboxProvider({ children }: { children: React.ReactNode }) {
  const { account, getApiToken } = useAuth();
  const { isAdmin, ready } = useRole();
  const { toast } = useToast();
  const email = account?.username ?? "";

  const [mine, setMine] = useState<Sandbox[]>([]);
  const [all, setAll] = useState<Sandbox[]>([]);
  const [extensionRequests, setExtensionRequests] = useState<ExtensionRequest[]>([]);
  const [allNotifications, setNotifications] = useState<Notification[]>(initialNotifications);
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
      const [own, every, extensions] = await Promise.all([
        apiFetch<Sandbox[]>(getToken, "/sandboxes"),
        isAdmin ? apiFetch<Sandbox[]>(getToken, "/admin/sandboxes") : Promise.resolve<Sandbox[]>([]),
        isAdmin
          ? apiFetch<ExtensionRequest[]>(getToken, "/extensions")
          : Promise.resolve<ExtensionRequest[]>([]),
      ]);
      setMine(own.map(withPlaceholderSpend));
      setAll(every.map(withPlaceholderSpend));
      setExtensionRequests(extensions);
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

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const tick = async () => {
      if (!cancelled) await load();
    };
    void tick();
    const timer = setInterval(tick, busy ? BUSY_POLL_MS : IDLE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [ready, load, busy]);

  const isMine = useCallback(
    (address: string) => {
      const a = address.toLowerCase();
      return a.includes(DEMO_REQUESTOR_EMAIL) || (email !== "" && a.includes(email.toLowerCase()));
    },
    [email]
  );

  // Notifications stay local/demo until email notifications are built.
  const notifications = useMemo(
    () => allNotifications.filter((n) => isMine(n.to)),
    [allNotifications, isMine]
  );

  const notify = useCallback((n: Omit<Notification, "id" | "when">) => {
    setNotifications((prev) => [{ ...n, id: `n${Date.now()}`, when: nowStamp() }, ...prev]);
  }, []);

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
    async (req: NewRequest) => {
      const created = await run(() => post<Sandbox>("/sandboxes", req));
      if (created) {
        notify({ category: "Approval", title: `Sandbox request submitted — ${created.name}`, to: created.owner });
      }
      return created;
    },
    [run, post, notify]
  );

  const requestExtension = useCallback(
    async (id: string, days: ExtensionRequest["extraDays"], reason: string) => {
      const ext = await run(() =>
        post<ExtensionRequest>(`/sandboxes/${path(id)}/extensions`, { extraDays: days, reason })
      );
      if (ext) {
        notify({
          category: "Approval",
          title: `Extension requested (+${days} days) — ${ext.sandboxName}`,
          to: ext.requestorEmail,
        });
      }
      return ext !== null;
    },
    [run, post, notify]
  );

  const decommissionRequested = useCallback(
    async (id: string, reason: string) => {
      const s = await run(() => post<Sandbox>(`/sandboxes/${path(id)}/decommission`, { reason }));
      if (s) notify({ category: "Approval", title: `Decommission requested — ${s.name}`, to: s.owner });
      return s !== null;
    },
    [run, post, notify]
  );

  const approveRequest = useCallback(
    async (id: string, budgetOverride?: number) =>
      (await run(() => post(`/approvals/${path(id)}/approve`, { budget: budgetOverride }))) !== null,
    [run, post]
  );

  const rejectRequest = useCallback(
    async (id: string, reason: string) => {
      const s = await run(() => post<Sandbox>(`/approvals/${path(id)}/reject`, { reason }));
      if (s) notify({ category: "Approval", title: `Sandbox request rejected - ${id}`, to: s.requestorEmail });
      return s !== null;
    },
    [run, post, notify]
  );

  const retryProvisioning = useCallback(
    async (id: string) => (await run(() => post(`/admin/sandboxes/${path(id)}/retry`))) !== null,
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

  const value = useMemo(
    () => ({
      sandboxes: mine,
      notifications,
      adminRequests: all,
      extensionRequests,
      isLoading,
      error,
      refresh: load,
      addRequest,
      requestExtension,
      decommissionRequested,
      approveRequest,
      rejectRequest,
      retryProvisioning,
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
      isLoading,
      error,
      load,
      addRequest,
      requestExtension,
      decommissionRequested,
      approveRequest,
      rejectRequest,
      retryProvisioning,
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

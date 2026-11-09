"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LogOut, RotateCw } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import ThemeToggle from "@/components/ui/ThemeToggle";
import Skeleton from "@/components/ui/Skeleton";
import { useRole } from "@/hooks/useRole";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface AuthMe {
  authenticated: boolean;
  user_id: string | null;
  tenant_id: string | null;
  name: string | null;
  email: string | null;
  roles: string[];
  scopes: string[];
}

type MeErrorKind = "token" | "http" | "network";

type MeState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "redirecting" }
  | { status: "success"; data: AuthMe }
  | { status: "error"; kind: MeErrorKind; message: string };

const errorLabels: Record<MeErrorKind, string> = {
  token: "Token error",
  http: "API error",
  network: "Network error",
};

function initials(name?: string) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}

function MeRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold tracking-wide text-muted uppercase">{label}</dt>
      <dd className="mt-0.5 font-mono text-[11px] break-all text-foreground">{value || "—"}</dd>
    </div>
  );
}

function MeList({ items }: { items: string[] }) {
  if (items.length === 0) return <>—</>;
  return (
    <span className="flex flex-wrap gap-1">
      {items.map((item) => (
        <span key={item} className="border border-border bg-surface-2 px-1.5 py-0.5 font-sans">
          {item}
        </span>
      ))}
    </span>
  );
}

export default function ProfileMenu() {
  const { account, logout, getApiToken } = useAuth();
  const { isAdmin } = useRole();
  const [open, setOpen] = useState(false);
  const [me, setMe] = useState<MeState>({ status: "idle" });
  const ref = useRef<HTMLDivElement>(null);

  const loadMe = useCallback(async () => {
    setMe({ status: "loading" });

    let token: string | null;
    try {
      token = await getApiToken();
    } catch (err) {
      setMe({
        status: "error",
        kind: "token",
        message: err instanceof Error ? err.message : "Could not acquire an API access token.",
      });
      return;
    }

    // null means MSAL is redirecting to Microsoft for interaction
    if (!token) {
      setMe({ status: "redirecting" });
      return;
    }

    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
    } catch {
      setMe({
        status: "error",
        kind: "network",
        message: `Cannot reach the API at ${API_BASE_URL}. Check that the backend is running and allows this origin.`,
      });
      return;
    }

    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        // non-JSON error body; keep statusText
      }
      setMe({ status: "error", kind: "http", message: `${res.status} ${detail}`.trim() });
      return;
    }

    try {
      setMe({ status: "success", data: (await res.json()) as AuthMe });
    } catch {
      setMe({ status: "error", kind: "http", message: "The API returned an invalid response." });
    }
  }, [getApiToken]);

  const toggleMenu = () => {
    const next = !open;
    setOpen(next);
    if (next && me.status === "idle") void loadMe();
  };

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={toggleMenu}
        aria-label="Open profile menu"
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex h-10 w-10 items-center justify-center bg-surface-2 text-sm font-semibold text-accent transition hover:brightness-110"
      >
        {initials(account?.name)}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-80 border border-border bg-surface shadow-card"
        >
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-semibold text-foreground">{account?.name}</p>
              {isAdmin && (
                <span className="shrink-0 border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-accent-dark dark:text-accent-light">
                  IT Admin
                </span>
              )}
            </div>
            <p className="truncate text-xs text-muted">{account?.username}</p>
          </div>

          <div className="border-b border-border px-4 py-3" aria-live="polite">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-foreground">Backend session</span>
              <button
                onClick={() => void loadMe()}
                disabled={me.status === "loading" || me.status === "redirecting"}
                aria-label="Refresh backend session"
                className="text-muted transition hover:text-accent disabled:opacity-40"
              >
                <RotateCw size={14} className={me.status === "loading" ? "animate-spin" : ""} />
              </button>
            </div>

            {(me.status === "idle" || me.status === "loading") && (
              <div className="space-y-2" aria-busy="true" aria-label="Loading backend session">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            )}

            {me.status === "redirecting" && (
              <p className="text-xs text-muted">Redirecting to Microsoft sign-in…</p>
            )}

            {me.status === "error" && (
              <div role="alert" className="border border-red-500/30 bg-red-500/10 px-3 py-2">
                <p className="text-xs font-semibold text-red-700 dark:text-red-400">
                  {errorLabels[me.kind]}
                </p>
                <p className="mt-0.5 text-xs break-words text-red-700 dark:text-red-400">{me.message}</p>
              </div>
            )}

            {me.status === "success" && (
              <dl className="space-y-2">
                <MeRow label="Name" value={me.data.name} />
                <MeRow label="Email" value={me.data.email} />
                <MeRow label="User ID" value={me.data.user_id} />
                <MeRow label="Tenant ID" value={me.data.tenant_id} />
                <MeRow label="Roles" value={<MeList items={me.data.roles} />} />
                <MeRow label="Scopes" value={<MeList items={me.data.scopes} />} />
              </dl>
            )}
          </div>

          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <span className="text-sm text-foreground">Theme</span>
            <ThemeToggle />
          </div>

          <button
            role="menuitem"
            onClick={logout}
            className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm text-foreground transition hover:bg-surface-2"
          >
            <LogOut size={16} className="text-muted" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

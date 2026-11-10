"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { InteractionStatus } from "@azure/msal-browser";
import { LogOut, RefreshCw } from "lucide-react";
import { ADMIN_ROLE } from "@/config/roles";
import { useAuth } from "@/hooks/useAuth";
import { RoleContext } from "@/hooks/useRole";
import { apiFetch } from "@/lib/api";

export default function RoleProvider({ children }: { children: React.ReactNode }) {
  const { account, getApiToken, inProgress, logout } = useAuth();
  const accountId = account?.homeAccountId ?? "";
  const tokenRef = useRef(getApiToken);
  const [profile, setProfile] = useState<{ accountId: string; roles: string[]; budgetCurrency: string; error: string | null } | null>(null);

  useEffect(() => {
    tokenRef.current = getApiToken;
  });

  useEffect(() => {
    if (!accountId || inProgress !== InteractionStatus.None) return;
    let cancelled = false;
    apiFetch<{ roles: string[]; budget_currency: string }>(() => tokenRef.current(), "/auth/me")
      .then(({ roles, budget_currency }) => {
        if (!Array.isArray(roles) || roles.some((role) => typeof role !== "string")) throw new Error("Invalid role response.");
        if (!/^[A-Z]{3}$/.test(budget_currency)) throw new Error("Invalid budget currency response.");
        if (!cancelled) setProfile({ accountId, roles, budgetCurrency: budget_currency, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) setProfile({ accountId, roles: [], budgetCurrency: "INR", error: error instanceof Error ? error.message : "Unable to verify access." });
      });
    return () => { cancelled = true; };
  }, [accountId, inProgress]);

  const current = profile?.accountId === accountId ? profile : null;
  const roles = current?.roles ?? [];
  if (accountId && current?.error) {
    return (
      <div role="alert" className="mx-auto max-w-lg space-y-4 p-8">
        <h1 className="text-xl font-semibold">Unable to verify access</h1>
        <p className="break-words text-sm">{current.error}</p>
        <div className="flex gap-4">
          <button onClick={() => window.location.reload()} className="flex items-center gap-2"><RefreshCw size={16} />Retry</button>
          <button onClick={() => void logout()} className="flex items-center gap-2"><LogOut size={16} />Sign out</button>
        </div>
      </div>
    );
  }
  return (
    <RoleContext.Provider value={{ roles, isAdmin: roles.includes(ADMIN_ROLE), ready: !!accountId && !!current, budgetCurrency: current?.budgetCurrency ?? "INR" }}>
      {accountId && !current ? <div role="status" className="p-8 text-sm">Verifying access...</div> : <Fragment key={accountId}>{children}</Fragment>}
    </RoleContext.Provider>
  );
}
"use client";

import { createContext, useContext } from "react";

export const RoleContext = createContext({ roles: [] as string[], isAdmin: false, ready: false, budgetCurrency: "USD" });

export function useRole() {
  return useContext(RoleContext);
}

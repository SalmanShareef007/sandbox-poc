"use client";

import { useMemo } from "react";
import { useAuth } from "@/hooks/useAuth";
import { ADMIN_ROLE } from "@/config/roles";

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((v) => typeof v === "string");

export function useRole() {
  const { account } = useAuth();
  const rawRoles: unknown = account?.idTokenClaims?.roles;

  const roles = useMemo(() => (isStringArray(rawRoles) ? rawRoles : []), [rawRoles]);

  return {
    roles,
    isAdmin: roles.includes(ADMIN_ROLE),
    ready: account !== null,
  };
}

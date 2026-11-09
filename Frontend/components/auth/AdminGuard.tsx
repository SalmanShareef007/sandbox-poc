"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useRole } from "@/hooks/useRole";

export default function AdminGuard({ children }: { children: React.ReactNode }) {
  const { isAdmin, ready } = useRole();
  const router = useRouter();

  useEffect(() => {
    if (ready && !isAdmin) router.replace("/dashboard");
  }, [ready, isAdmin, router]);

  if (!ready || !isAdmin) return null;

  return <>{children}</>;
}

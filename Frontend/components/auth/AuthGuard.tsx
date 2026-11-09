"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { InteractionStatus } from "@azure/msal-browser";
import { useAuth } from "@/hooks/useAuth";

export default function AuthGuard({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, inProgress } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Only redirect once MSAL has finished any login/token work
    if (inProgress === InteractionStatus.None && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, inProgress, router]);

  if (!isAuthenticated) return null; // swap for a spinner later

  return <>{children}</>;
}
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus } from "lucide-react";
import MobileNav from "@/components/layout/MobileNav";
import ProfileMenu from "@/components/layout/ProfileMenu";
import { useRole } from "@/hooks/useRole";
const titles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/requests/new": "New sandbox request",
  "/sandboxes": "Sandboxes",
  "/notifications": "Notifications",
  "/help": "Help & FAQ",
  "/admin": "Admin overview",
  "/admin/approvals": "Approvals",
  "/admin/extensions": "Extension requests",
  "/admin/sandboxes": "All sandboxes",
  "/admin/costs": "Costs",
};

export default function Topbar() {
  const pathname = usePathname();
  const { isAdmin, ready } = useRole();
  const title =
    titles[pathname] ?? (pathname.startsWith("/sandboxes/") ? "Sandbox details" : "");

  return (
    <header className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-border bg-surface/90 px-8 backdrop-blur">
      <div className="flex items-center gap-3">
        <MobileNav />
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
      </div>

      <div className="flex items-center gap-4">
        {ready && !isAdmin && (
          <Link
            href="/requests/new"
            className="bg-accent-gradient flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110"
          >
            <Plus size={16} />
            New request
          </Link>
        )}

        <ProfileMenu />
      </div>
    </header>
  );
}
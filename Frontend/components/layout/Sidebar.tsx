"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isActivePath, navSections, type NavItemDef } from "@/components/layout/navItems";
import { useRole } from "@/hooks/useRole";
import { useSandboxes } from "@/components/providers/SandboxProvider";

export function NavItem({
  href,
  label,
  icon: Icon,
  exact,
  badgeCount = 0,
}: NavItemDef & { badgeCount?: number }) {
  const pathname = usePathname();
  const active = isActivePath(pathname, href, exact);

  return (
    <Link
      href={href}
      className={`flex items-center justify-between gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${
        active
          ? "bg-accent-gradient text-white shadow-accent"
          : "text-muted hover:bg-surface-2 hover:text-foreground"
      }`}
    >
      <span className="flex items-center gap-3">
        <Icon size={18} />
        {label}
      </span>
      {badgeCount > 0 && (
        <span
          aria-label={`${badgeCount} unread notifications`}
          title={`${badgeCount} unread notifications`}
          className="min-w-5 rounded-full bg-red-600 px-1.5 py-0.5 text-center text-xs font-bold leading-4 text-white"
        >
          {badgeCount > 99 ? "99+" : badgeCount}
        </span>
      )}
    </Link>
  );
}

export function NavSections() {
  const { isAdmin, ready } = useRole();
  const { notifications } = useSandboxes();
  if (!ready) return null;
  const unreadCount = notifications.filter((notification) => !notification.read).length;

  return (
    <>
      {navSections(isAdmin).map((section, i) => (
        <div key={section.title}>
          <p
            className={`${i === 0 ? "mt-6" : "mt-8"} mb-2 px-4 text-xs font-semibold tracking-wider text-muted`}
          >
            {section.title}
          </p>
          <nav className="space-y-1" aria-label={section.title.toLowerCase()}>
            {section.items.map((item) => (
              <NavItem
                key={item.href}
                {...item}
                badgeCount={item.href === "/notifications" ? unreadCount : undefined}
              />
            ))}
          </nav>
        </div>
      ))}
    </>
  );
}

export default function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-surface p-4 md:flex">
      <div className="px-2 py-4">
        <div className="flex items-center gap-3 px-2 py-2">
          <span aria-hidden="true" className="h-9 w-1.5 bg-accent" />
          <span className="text-lg leading-tight font-bold text-foreground">
            Azure Sandbox
          </span>
        </div>
      </div>

      <NavSections />
    </aside>
  );
}
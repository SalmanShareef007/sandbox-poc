import {
  Bell,
  Box,
  Boxes,
  CalendarClock,
  CircleQuestionMark,
  ClipboardCheck,
  Home,
  LayoutDashboard,
  Plus,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface NavItemDef {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Only highlight on an exact path match (for parent routes like /admin). */
  exact?: boolean;
}

export interface NavSection {
  title: string;
  items: NavItemDef[];
}

const helpItem: NavItemDef = { href: "/help", label: "Help", icon: CircleQuestionMark };

export const workspaceNav: NavItemDef[] = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/requests/new", label: "New request", icon: Plus },
  { href: "/sandboxes", label: "My sandboxes", icon: Box },
];

export const activityNav: NavItemDef[] = [
  { href: "/notifications", label: "Notifications", icon: Bell },
  helpItem,
];

export const adminNav: NavItemDef[] = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/admin/approvals", label: "Approvals", icon: ClipboardCheck },
  { href: "/admin/extensions", label: "Extensions", icon: CalendarClock },
  { href: "/admin/sandboxes", label: "All sandboxes", icon: Boxes },
  { href: "/admin/costs", label: "Costs", icon: Wallet },
];

export const navSections = (isAdmin: boolean): NavSection[] =>
  isAdmin
    ? [
        { title: "ADMIN", items: adminNav },
        { title: "SUPPORT", items: [helpItem] },
      ]
    : [
        { title: "WORKSPACE", items: workspaceNav },
        { title: "ACTIVITY", items: activityNav },
      ];

export const isActivePath = (pathname: string, href: string, exact = false) =>
  pathname === href || (!exact && pathname.startsWith(href + "/"));

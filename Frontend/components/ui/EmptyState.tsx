import Link from "next/link";
import type { LucideIcon } from "lucide-react";

type EmptyStateAction =
  | { label: string; href: string; onClick?: never }
  | { label: string; onClick: () => void; href?: never };

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  text: string;
  action?: EmptyStateAction;
}

const actionCls =
  "bg-accent-gradient mt-6 inline-flex items-center px-5 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110";

export default function EmptyState({ icon: Icon, title, text, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <Icon size={36} className="text-muted" />
      <p className="mt-4 font-semibold text-foreground">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted">{text}</p>
      {action &&
        (action.href !== undefined ? (
          <Link href={action.href} className={actionCls}>
            {action.label}
          </Link>
        ) : (
          <button onClick={action.onClick} className={actionCls}>
            {action.label}
          </button>
        ))}
    </div>
  );
}

import RequestorGuard from "@/components/auth/RequestorGuard";

export default function RequestorLayout({ children }: { children: React.ReactNode }) {
  return <RequestorGuard>{children}</RequestorGuard>;
}

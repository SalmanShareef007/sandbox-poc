import type { Metadata } from "next";
import MsalProviderWrapper from "@/components/auth/MsalProviderWrapper";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sandbox UI",
  description: "MSAL auth sandbox",
};
export const instant = false;

// Runs before paint so the saved theme applies without a flash.
const themeScript = `
(function () {
  try {
    var t = localStorage.getItem("theme");
    if (!t) t = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <MsalProviderWrapper>{children}</MsalProviderWrapper>
      </body>
    </html>
  );
}
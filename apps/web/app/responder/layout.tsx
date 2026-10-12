import type { Metadata, Viewport } from "next";

// The team app is installable (PRD P1 #7: Chrome's criteria are HTTPS + a manifest with icons, start_url and
// display). Only here: the family's reporter page must not install as the team's app.
export const metadata: Metadata = {
  title: "RakshaSetu · Team",
  manifest: "/responder.webmanifest",
  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },
};
export const viewport: Viewport = { themeColor: "#111111" };

export default function ResponderLayout({ children }: { children: React.ReactNode }) {
  return children;
}

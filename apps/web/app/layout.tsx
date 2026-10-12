import type { Metadata, Viewport } from "next";
import "@fontsource/noto-sans/400.css";
import "@fontsource/noto-sans/500.css";
import "@fontsource/noto-sans/600.css";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "./globals.css";

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#ffffff" };

export const metadata: Metadata = {
  title: "RakshaSetu",
  description: "Never lost. Never doubled. Never stale.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

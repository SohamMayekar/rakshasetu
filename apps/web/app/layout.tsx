import type { Metadata, Viewport } from "next";
import "@fontsource/noto-sans/400.css";
import "@fontsource/noto-sans/500.css";
import "@fontsource/noto-sans/600.css";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "@fontsource/instrument-serif/400-italic.css";
import "./globals.css";
import "./landing.css";

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#efeeea" };

export const metadata: Metadata = {
  title: "RakshaSetu | One command layer for every emergency",
  description: "National incident command for any disaster: reports from calls, voice, messages and sheets become one case each, with one accountable team, followed until the people are confirmed safe.",
};

const MOTION_BOOT = `(function(){var d=document.documentElement;try{var q=new URLSearchParams(location.search).get("motion");var r=q==="reduced"||(q!=="full"&&matchMedia("(prefers-reduced-motion: reduce)").matches);d.dataset.motion=r?"reduced":"full";}catch(e){d.dataset.motion="full";}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: MOTION_BOOT }} /></head>
      <body>{children}</body>
    </html>
  );
}

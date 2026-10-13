import type { Metadata, Viewport } from "next";
import "@fontsource/noto-sans/400.css";
import "@fontsource/noto-sans/500.css";
import "@fontsource/noto-sans/600.css";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "@fontsource-variable/archivo";
import "@fontsource-variable/plus-jakarta-sans";
import "@fontsource/instrument-serif/400-italic.css";
import "./globals.css";
import "./landing.css";

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#efeeea" };

export const metadata: Metadata = {
  title: "RakshaSetu | One family. One team. Until safe.",
  description: "A district rescue-request desk that connects a family's report with a response team and follows the case through to family confirmation.",
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

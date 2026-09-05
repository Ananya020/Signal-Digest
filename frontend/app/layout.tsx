import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const ibmPlexSans = IBM_Plex_Sans({
  variable: "--font-ibm-plex-sans",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
});

const plusJakartaSans = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Signal Digest",
  description: "Statistically-aware market watchlist with live fault-injection demo.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${ibmPlexSans.variable} ${ibmPlexMono.variable} ${plusJakartaSans.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-canvas font-sans text-ink">{children}</body>
    </html>
  );
}

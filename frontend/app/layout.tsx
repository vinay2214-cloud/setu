import type { Metadata } from "next";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/fraunces/500.css";
import "@fontsource/noto-sans-telugu/400.css";
import "@fontsource/noto-sans-devanagari/400.css";
import "./globals.css";
import { QueryProvider } from "@/components/setu/query-provider";

export const metadata: Metadata = {
  title: "Setu · Care continuity",
  description: "Synthetic post-discharge care continuity prototype",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><QueryProvider>{children}</QueryProvider></body></html>;
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Setu · Care continuity",
  description: "Synthetic post-discharge care continuity prototype",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

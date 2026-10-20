import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "VideoMind AI — From video to understanding",
  description: "Turn educational videos into clear transcripts and focused study notes.",
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}

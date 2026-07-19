import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Shapez2 TMAM Studio",
  description: "브라우저에서 실행되는 Shapez 2 도형 판정·분석·제작 과정 도구입니다.",
  applicationName: "Shapez2 TMAM Studio",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg", apple: "/icon-192.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f0f0f0",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko" suppressHydrationWarning><body>{children}</body></html>;
}

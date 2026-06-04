import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DNGun Internal Console",
  description: "Internal prospect intelligence console for DNGun MVP 0.3"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

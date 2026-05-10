import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Guardian-Stream Dashboard",
  description:
    "Observability for the Guardian-Stream agent: prompt history, reasoning traces, verification verdicts.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

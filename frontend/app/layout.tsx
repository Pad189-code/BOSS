import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Boss — Validation des offres",
  description: "Dashboard employé pour valider les offres générées par l'agent IA",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}

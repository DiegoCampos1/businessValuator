import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Business Valuator",
  description: "Análise fundamentalista de ações da B3",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" className="dark">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        {children}
      </body>
    </html>
  );
}

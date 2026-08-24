import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "CorpusForge",
  description: "Operational dashboard for CorpusForge"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Accord | Procurement workspace",
  description: "Turn supplier quotes into procurement decisions.",
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

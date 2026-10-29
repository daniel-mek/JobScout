import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ApplyOS · Find your next role",
  description:
    "Discover jobs, understand your matches, and track your applications.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}

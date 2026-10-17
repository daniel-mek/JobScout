import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ApplyOS · Your next chapter",
  description: "A considered approach to your early-career job search.",
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

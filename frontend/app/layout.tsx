import type { Metadata, Viewport } from "next";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARIA",
  description: "Your personal AI assistant",
  appleWebApp: {
    capable: true,
    title: "ARIA",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#09090b",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {process.env.NODE_ENV === "development" && (
          <Script
            src="https://unpkg.com/react-grab@0.1.37/dist/index.global.js"
            crossOrigin="anonymous"
            strategy="lazyOnload"
            data-options={JSON.stringify(
              { activationMode: "toggle", allowActivationInsideInput: true, maxContextLines: 3 }
            )}
          />
        )}
      </head>
      <body>{children}</body>
    </html>
  );
}

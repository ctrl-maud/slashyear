import type { Metadata, Viewport } from "next";
import { Source_Serif_4 } from "next/font/google";
import { JsonLd, SITE } from "@/lib/seo";
import "./globals.css";

const serif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE.base),
  title: {
    default: "slashyear — every recorded year, every line sourced",
    template: "%s",
  },
  description: SITE.blurb,
  applicationName: SITE.name,
  robots: { index: true, follow: true, "max-snippet": -1, "max-image-preview": "large" },
  openGraph: { siteName: SITE.name, type: "website", locale: "en_US" },
  twitter: { card: "summary" },
};

export const viewport: Viewport = {
  themeColor: "#f8f7f5",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={serif.variable}>
      <head>
        <JsonLd
          data={{
            "@context": "https://schema.org",
            "@type": "WebSite",
            name: SITE.name,
            alternateName: "/year",
            url: SITE.base,
            description: SITE.blurb,
            inLanguage: "en",
            license: "https://creativecommons.org/licenses/by-sa/4.0/",
            isBasedOn: "https://en.wikipedia.org/",
          }}
        />
      </head>
      <body className="font-serif antialiased">{children}</body>
    </html>
  );
}

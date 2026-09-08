import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  // metadataBase makes relative OG/twitter image URLs resolve to the real host
  // instead of localhost when Next renders social preview tags.
  metadataBase: new URL("https://nirnaylegal.in"),
  title: "Nirnay Legal — Search Indian case law by meaning",
  description:
    "Semantic search across 25,000+ Supreme Court and High Court judgments. Ask a question, get the passages that answer it.",
  openGraph: {
    title: "Nirnay Legal — Search Indian case law by meaning",
    description:
      "Semantic search across 25,000+ Supreme Court and High Court judgments.",
    url: "https://nirnaylegal.in",
    siteName: "Nirnay Legal",
    locale: "en_IN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Nirnay Legal — Search Indian case law by meaning",
    description:
      "Semantic search across 25,000+ Supreme Court and High Court judgments.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}

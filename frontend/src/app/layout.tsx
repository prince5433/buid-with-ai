import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "DocIntel AI — Document Intelligence & RAG",
  description: "AI-powered document parsing, classification, and question answering with grounded citations. Upload documents and chat with your knowledge base.",
  keywords: ["document intelligence", "RAG", "AI", "chatbot", "document parsing", "OCR"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        {children}
      </body>
    </html>
  );
}

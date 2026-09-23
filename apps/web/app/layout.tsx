import type { Metadata } from "next";
import { Prompt } from "next/font/google";
import NavBar from "@/shared/NavBar";
import "./globals.css";

const prompt = Prompt({ subsets: ["thai", "latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = { title: "rod-mai-rod" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th">
      <body className={prompt.className}>
        <NavBar />
        <main className="page">{children}</main>
      </body>
    </html>
  );
}

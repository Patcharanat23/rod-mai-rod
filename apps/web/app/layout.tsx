import type { Metadata } from "next";
import { Prompt, Fraunces, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import Shell from "@/components/Shell";
import { AppProvider } from "@/lib/store";
import { ChatProvider } from "@/lib/chat";

const prompt = Prompt({
  subsets: ["thai", "latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-prompt",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-serif",
  display: "swap",
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "รอดไม่รอด · ระบบวางแผนเดินทางปลอดภัย",
  description: "ระบบวิเคราะห์สภาพอากาศและจุดเสี่ยงภัยตลอดเส้นทางแบบเรียลไทม์ พร้อมน้องกิเลน AI ผู้ช่วยเดินทาง",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th" className={`${prompt.variable} ${fraunces.variable} ${jakarta.variable}`}>
      <body className={prompt.className}>
        <AppProvider>
          <ChatProvider>
            <Shell>{children}</Shell>
          </ChatProvider>
        </AppProvider>
      </body>
    </html>
  );
}


import type { Metadata } from "next";
import { Inter, VT323 } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const vt323 = VT323({ weight: "400", subsets: ["latin"], variable: "--font-vt323" });

export const metadata: Metadata = {
  title: "SkyBlock Bazaar Oracle",
  description: "AI-powered Hypixel Skyblock Investment Engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${vt323.variable} font-sans antialiased bg-[#09090b] text-zinc-100`}>
        <nav className="border-b border-zinc-800 bg-[#09090b]/80 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[#39FF14] text-xl font-vt323 tracking-wider">BAZAAR ORACLE</span>
            </div>
            <div className="flex gap-6 text-sm font-medium">
              <a href="/" className="hover:text-[#39FF14] transition-colors">Dashboard</a>
              <a href="/planner" className="hover:text-[#39FF14] transition-colors">Optimizer</a>
              <a href="/history" className="hover:text-[#39FF14] transition-colors">My Logs</a>
            </div>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto p-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}

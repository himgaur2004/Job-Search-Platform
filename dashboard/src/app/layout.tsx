import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/Navigation";

const jakarta = Plus_Jakarta_Sans({ 
  subsets: ["latin"], 
  variable: "--font-jakarta" 
});

export const metadata: Metadata = {
  title: "Nexus | AI Job Agent",
  description: "Autonomous job hunting and outreach platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${jakarta.variable} font-sans antialiased flex`}>
        <Navigation />
        <main className="flex-1 min-h-screen w-full" style={{ paddingLeft: "80px" }}>
          <div className="max-w-[1400px] mx-auto p-6 md:p-10 lg:p-12">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}

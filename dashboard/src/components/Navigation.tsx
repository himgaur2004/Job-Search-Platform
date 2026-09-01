"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Home, 
  Briefcase, 
  Rocket, 
  Mail, 
  FileText,
  Settings,
  LogOut,
  Hexagon
} from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

export function Navigation() {
  const pathname = usePathname();

  const links = [
    { href: "/", label: "Dashboard", icon: Home },
    { href: "/jobs", label: "Pipeline", icon: Briefcase },
    { href: "/auto-hunt", label: "Job Scout", icon: Rocket },
    { href: "/outreach", label: "Outreach", icon: Mail },
    { href: "/resumes", label: "Resumes", icon: FileText },
  ];

  const bottomLinks = [
    { href: "/settings", label: "Settings", icon: Settings },
    { href: "#", label: "Logout", icon: LogOut },
  ];

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-20 bg-obsidian-900 border-r border-white/[0.05] flex flex-col items-center py-6 z-50">
      {/* Logo */}
      <Link href="/" className="mb-10 group relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-violet-500">
        <Hexagon size={24} className="text-white fill-white/20" />
        <div className="absolute inset-0 bg-white/20 rounded-xl blur-md opacity-0 group-hover:opacity-100 transition-opacity" />
      </Link>

      {/* Main Nav */}
      <nav className="flex-1 w-full flex flex-col items-center gap-4">
        {links.map((link) => {
          const isActive = pathname === link.href;
          return (
            <Link 
              key={link.href} 
              href={link.href}
              className="relative group flex items-center justify-center w-12 h-12 rounded-xl transition-all"
            >
              {isActive && (
                <motion.div 
                  className="absolute inset-0 bg-white/[0.08] rounded-xl border border-white/[0.1]"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                />
              )}
              
              {isActive && (
                <div className="absolute -left-4 top-1/2 -translate-y-1/2 w-1 h-6 bg-cyan-400 rounded-r-full shadow-[0_0_10px_rgba(0,212,255,0.8)]" />
              )}
              
              <link.icon 
                size={20} 
                className={cn(
                  "relative z-10 transition-colors",
                  isActive ? "text-cyan-400" : "text-gray-500 group-hover:text-gray-300"
                )} 
              />

              {/* Tooltip */}
              <div className="absolute left-14 px-2.5 py-1.5 bg-obsidian-800 border border-white/10 rounded-md text-xs font-medium text-white opacity-0 -translate-x-2 pointer-events-none group-hover:opacity-100 group-hover:translate-x-0 transition-all z-50 whitespace-nowrap shadow-xl">
                {link.label}
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Bottom Nav */}
      <nav className="w-full flex flex-col items-center gap-4 mt-auto">
        {bottomLinks.map((link) => (
          <Link 
            key={link.label} 
            href={link.href}
            className="relative group flex items-center justify-center w-12 h-12 rounded-xl transition-all"
          >
            <link.icon 
              size={20} 
              className="text-gray-600 group-hover:text-gray-300 transition-colors" 
            />
            {/* Tooltip */}
            <div className="absolute left-14 px-2.5 py-1.5 bg-obsidian-800 border border-white/10 rounded-md text-xs font-medium text-white opacity-0 -translate-x-2 pointer-events-none group-hover:opacity-100 group-hover:translate-x-0 transition-all z-50 whitespace-nowrap shadow-xl">
              {link.label}
            </div>
          </Link>
        ))}
      </nav>
    </aside>
  );
}

"use client";

import React from "react";
import { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  delay?: number;
  color: "cyan" | "violet" | "emerald" | "amber" | "rose";
}

const colors = {
  cyan: { bg: "bg-cyan-500/10", text: "text-cyan-400", border: "group-hover:border-cyan-500/30", glow: "rgba(0,212,255,0.15)" },
  violet: { bg: "bg-violet-500/10", text: "text-violet-400", border: "group-hover:border-violet-500/30", glow: "rgba(139,92,246,0.15)" },
  emerald: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "group-hover:border-emerald-500/30", glow: "rgba(52,211,153,0.15)" },
  amber: { bg: "bg-amber-500/10", text: "text-amber-400", border: "group-hover:border-amber-500/30", glow: "rgba(251,191,36,0.15)" },
  rose: { bg: "bg-rose-500/10", text: "text-rose-400", border: "group-hover:border-rose-500/30", glow: "rgba(244,63,94,0.15)" },
};

export function StatCard({ label, value, icon: Icon, delay = 0, color }: StatCardProps) {
  const theme = colors[color];

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className={`glass-panel p-5 relative overflow-hidden group transition-all duration-300 hover:-translate-y-1 ${theme.border}`}
      style={{ boxShadow: `0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.02), 0 0 40px ${theme.glow} opacity-0` }}
    >
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-lg ${theme.bg}`}>
          <Icon size={16} className={theme.text} />
        </div>
        <span className="font-medium text-sm text-gray-300">{label}</span>
      </div>
      
      <div className="text-4xl font-extrabold text-white">
        {value}
      </div>
    </motion.div>
  );
}

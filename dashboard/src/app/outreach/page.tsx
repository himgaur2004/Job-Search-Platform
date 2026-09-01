"use client";

import { useState } from "react";
import { Mail, Send, CheckCircle2, Activity, Globe, Code2, Users } from "lucide-react";
import { motion } from "framer-motion";

export default function OutreachPage() {
  const [emails, setEmails] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const emailCount = emails.split(",").map(e => e.trim()).filter(e => e.includes("@")).length;

  const handleSubmit = async () => {
    if (!emails.trim()) return;
    setLoading(true);
    const emailList = emails.split(",").map(e => e.trim()).filter(e => e);

    try {
      const res = await fetch("/api/service2/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emails: emailList }),
      });
      if (res.ok) {
        setSuccess(true);
        setEmails("");
        setTimeout(() => setSuccess(false), 5000);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center gap-4 border-b border-white/[0.05] pb-6"
      >
        <div className="w-12 h-12 rounded-xl bg-violet-500/10 flex items-center justify-center">
          <Mail className="text-violet-400" size={24} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Outreach Engine</h1>
          <p className="text-sm text-gray-400 mt-1">Reverse-lookup cold email automation</p>
        </div>
      </motion.div>

      {/* Info Cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="grid grid-cols-3 gap-4"
      >
        {[
          { icon: Globe, label: "Profile", desc: "Scrapes domain homepage" },
          { icon: Code2, label: "Analyze", desc: "AI deduces tech stack" },
          { icon: Users, label: "Tailor", desc: "Customizes LaTeX resume" },
        ].map((item, i) => (
          <div key={i} className="glass-panel p-4 flex flex-col gap-2">
            <item.icon size={16} className="text-violet-400" />
            <div>
              <p className="text-white text-sm font-semibold">{item.label}</p>
              <p className="text-gray-500 text-xs mt-0.5">{item.desc}</p>
            </div>
          </div>
        ))}
      </motion.div>

      {/* Main Form */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="glass-panel-elevated p-8 relative overflow-hidden"
      >
        <div className="absolute -bottom-20 -left-20 w-64 h-64 bg-violet-500/10 rounded-full blur-[80px] pointer-events-none" />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="input-label mb-0">Target Recruiter Emails</label>
            {emailCount > 0 && (
              <span className="badge badge-violet">{emailCount} queued</span>
            )}
          </div>
          
          <textarea
            value={emails}
            onChange={(e) => setEmails(e.target.value)}
            className="input-field h-40 font-mono text-sm leading-relaxed resize-none"
            placeholder="hiring@stripe.com, recruiter@openai.com..."
            spellCheck={false}
          />
          <p className="text-xs text-gray-500">Comma-separated list of target emails.</p>
        </div>

        <div className="mt-8 pt-6 border-t border-white/[0.05] flex items-center justify-between">
          {success ? (
            <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1.5 rounded-lg text-sm font-medium">
              <CheckCircle2 size={16} /> Campaign launched
            </motion.div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Activity size={14} className="text-violet-500/50" />
              Executes asynchronously
            </div>
          )}

          <button onClick={handleSubmit} disabled={loading || emailCount === 0} className="btn-primary min-w-[140px]" style={{ background: "linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)", boxShadow: "0 4px 16px rgba(139,92,246,0.2)" }}>
            {loading ? <Activity className="animate-pulse" size={16} /> : <Send size={16} className="-ml-1" />}
            {loading ? "Queueing..." : "Launch Campaign"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { fetchSummary, fetchJobs } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { Send, MessageCircle, CalendarCheck, Target, Rocket, Mail, FileText, Briefcase, MapPin, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { Job, SummaryData } from "@/lib/types";

export default function Dashboard() {
  const [data, setData] = useState<SummaryData>({
    sent_today: 0,
    replies: 0,
    interviews: 0,
    success_rate: 0,
  });
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = () => {
      fetchSummary().then(setData).catch(console.error);
      fetchJobs(5, 0).then(setRecentJobs).catch(console.error).finally(() => setLoading(false));
    };
    
    loadData();
    const t = setInterval(loadData, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-3xl font-bold text-white mb-2">Command Center</h1>
        <p className="text-gray-400 text-sm">Ultra mode AI job agent dashboard UI design</p>
      </motion.div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard delay={0.1} label="Sent Today" value={data.sent_today} icon={Send} color="cyan" />
        <StatCard delay={0.2} label="Replies" value={data.replies} icon={MessageCircle} color="violet" />
        <StatCard delay={0.3} label="Interviews" value={data.interviews} icon={CalendarCheck} color="emerald" />
        <StatCard delay={0.4} label="Success Rate" value={`${data.success_rate.toFixed(0)}%`} icon={Target} color="amber" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Recent Pipeline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="lg:col-span-2 glass-panel-elevated p-6 flex flex-col"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold text-white">Recent Pipeline</h2>
            <Link href="/jobs" className="text-xs font-medium text-gray-400 hover:text-white transition-colors bg-white/[0.03] px-3 py-1.5 rounded-lg border border-white/[0.05]">
              View all
            </Link>
          </div>

          <div className="flex-1">
            {loading ? (
              <div className="h-full flex items-center justify-center py-20">
                <Loader2 className="animate-spin text-gray-500" />
              </div>
            ) : recentJobs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center py-20 text-center">
                <Briefcase size={32} className="text-gray-600 mb-4" />
                <p className="text-gray-400 font-medium">No recent jobs</p>
                <p className="text-gray-600 text-xs mt-1">Deploy Scout to populate pipeline</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentJobs.map((job) => {
                  const isMatch = job.match_score != null;
                  const score = isMatch ? (job.match_score! * 100).toFixed(0) + "%" : "N/A";
                  
                  return (
                    <div key={job.id} className="flex items-center justify-between p-4 rounded-xl hover:bg-white/[0.02] transition-colors border border-transparent hover:border-white/[0.05] group">
                      <div className="flex items-center gap-4 w-1/2">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500/20 to-violet-500/20 border border-cyan-500/20 flex items-center justify-center text-cyan-300 font-bold text-sm shrink-0">
                          {job.company.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <h3 className="text-white font-medium text-sm truncate">{job.company}</h3>
                          <p className="text-gray-500 text-xs truncate flex items-center gap-1 mt-0.5">
                            <span className="truncate max-w-[120px]">{job.title}</span>
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-4 w-1/2 justify-end">
                        <span className={`badge ${isMatch && job.match_score! > 0.6 ? 'badge-cyan' : 'badge-neutral'} min-w-[60px] justify-center`}>
                          {score} Match
                        </span>
                        
                        {job.stage && !['sent', 'failed'].includes(job.status || '') ? (
                          <div className="flex items-center gap-1.5 text-xs text-cyan-400 bg-cyan-400/10 border border-cyan-400/20 px-2 py-1 rounded-lg">
                            <Loader2 size={12} className="animate-spin" />
                            {job.stage}
                          </div>
                        ) : (
                          <span className={`badge ${
                            job.status === "sent" ? "badge-emerald" :
                            job.status === "failed" ? "badge-rose" :
                            job.recruiter_email?.startsWith("needs") ? "badge-amber" :
                            "badge-violet"
                          } w-[80px] justify-center capitalize`}>
                            {job.status === "sent" ? "Sent" : job.status === "failed" ? "Failed" : job.recruiter_email?.startsWith("needs") ? "Action" : "Queued"}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </motion.div>

        {/* Right Column: Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="flex flex-col gap-4"
        >
          <h2 className="text-lg font-bold text-white mb-2">Quick Actions</h2>

          <Link href="/auto-hunt" className="glass-panel p-5 group hover:border-cyan-500/30 transition-all flex flex-col gap-3 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center">
              <Rocket size={16} className="text-cyan-400" />
            </div>
            <div>
              <h3 className="text-white font-medium text-sm">Deploy Scout</h3>
              <p className="text-gray-500 text-xs mt-1">Autonomous LinkedIn scraping</p>
            </div>
          </Link>

          <Link href="/outreach" className="glass-panel p-5 group hover:border-violet-500/30 transition-all flex flex-col gap-3 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
            <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
              <Mail size={16} className="text-violet-400" />
            </div>
            <div>
              <h3 className="text-white font-medium text-sm">Launch Outreach</h3>
              <p className="text-gray-500 text-xs mt-1">Targeted reverse-lookup emails</p>
            </div>
          </Link>

          <Link href="/resumes" className="glass-panel p-5 group hover:border-emerald-500/30 transition-all flex flex-col gap-3 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <FileText size={16} className="text-emerald-400" />
            </div>
            <div>
              <h3 className="text-white font-medium text-sm">Manage Resumes</h3>
              <p className="text-gray-500 text-xs mt-1">Dynamic LaTeX templates</p>
            </div>
          </Link>

          <Link href="/templates" className="glass-panel p-5 group hover:border-orange-500/30 transition-all flex flex-col gap-3 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-orange-500 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />
            <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <Mail size={16} className="text-orange-400" />
            </div>
            <div>
              <h3 className="text-white font-medium text-sm">Manage Templates</h3>
              <p className="text-gray-500 text-xs mt-1">Dynamic email templates</p>
            </div>
          </Link>
        </motion.div>
      </div>
    </div>
  );
}

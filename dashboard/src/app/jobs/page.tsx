"use client";

import { useEffect, useState } from "react";
import { fetchJobs, autoApply } from "@/lib/api";
import { Briefcase, Loader2, Send, Clock, CheckCircle2, XCircle, Search, ExternalLink, Play, Trash2 } from "lucide-react";
import { Job } from "@/lib/types";
import { motion } from "framer-motion";
import Link from "next/link";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [resumeEmail, setResumeEmail] = useState<Record<number, string>>({});
  const [resuming, setResuming] = useState<Record<number, boolean>>({});
  const [resumeMode, setResumeMode] = useState<Record<number, "prebuilt" | "generate">>({});

  // Debounce search input — 300ms delay before hitting API
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const loadJobs = async (q?: string) => {
    try {
      const data = await fetchJobs(500, 0, q || undefined);
      setJobs(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    loadJobs(debouncedSearch);
    const t = setInterval(() => loadJobs(debouncedSearch), 5000);
    return () => clearInterval(t);
  }, [debouncedSearch]);

  const handleResume = async (jobId: number) => {
    const email = resumeEmail[jobId];
    if (!email || !email.includes("@")) return alert("Invalid email");
    
    setResuming(prev => ({...prev, [jobId]: true}));
    try {
      const res = await fetch(`/api/jobs/${jobId}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setResumeEmail(prev => ({...prev, [jobId]: ""}));
        loadJobs(debouncedSearch);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setResuming(prev => ({...prev, [jobId]: false}));
    }
  };

  const handleAutoApply = async (jobId: number, url: string) => {
    setResuming(prev => ({...prev, [jobId]: true}));
    const mode = resumeMode[jobId] || "prebuilt";
    try {
      await autoApply(jobId, url, mode);
      loadJobs(debouncedSearch); // refresh immediately to show "Applying" state
    } catch (e) {
      console.error(e);
      alert("Failed to start auto-apply");
    } finally {
      setResuming(prev => ({...prev, [jobId]: false}));
    }
  };

  const toggleResumeMode = (jobId: number) => {
    setResumeMode(prev => ({
      ...prev,
      [jobId]: prev[jobId] === "generate" ? "prebuilt" : "generate",
    }));
  };

  const handleClearDb = async () => {
    if (!confirm("Are you sure you want to delete all jobs? This cannot be undone.")) return;
    setLoading(true);
    try {
      await fetch("/api/jobs", { method: "DELETE" });
      await loadJobs(debouncedSearch);
    } catch (e) {
      console.error(e);
      alert("Failed to clear database");
    } finally {
      setLoading(false);
    }
  };

  const filteredJobs = jobs.filter(j => {
    if (filter === "ats" && !j.source?.startsWith("ats_")) return false;
    if (filter === "job_boards" && j.source?.startsWith("ats_")) return false;
    if (filter === "needs_email" && !j.recruiter_email?.startsWith("needs")) return false;
    if (filter === "sent" && j.status !== "sent") return false;
    if (filter === "failed" && j.status !== "failed") return false;
    // Search is now server-side — no client-side filtering needed
    return true;
  });

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center gap-4 border-b border-white/[0.05] pb-6"
      >
        <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
          <Briefcase className="text-blue-400" size={24} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Jobs Pipeline</h1>
          <p className="text-sm text-gray-400 mt-1">
            {loading ? "Loading..." : `${filteredJobs.length} of ${jobs.length} jobs`}
          </p>
        </div>
        <div className="ml-auto">
          <button
            onClick={handleClearDb}
            disabled={loading}
            className="flex items-center gap-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 px-4 py-2 rounded-xl text-sm font-semibold transition-all disabled:opacity-50"
          >
            <Trash2 size={16} />
            Clear DB
          </button>
        </div>
      </motion.div>

      {/* Toolbar */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
      >
        <div className="flex bg-white/[0.02] p-1 rounded-xl border border-white/[0.05] overflow-x-auto whitespace-nowrap hide-scrollbar">
          {["all", "ats", "job_boards", "needs_email", "sent", "failed"].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize transition-all flex-shrink-0 ${
                filter === f 
                  ? "bg-white/[0.08] text-white shadow-sm" 
                  : "text-gray-500 hover:text-gray-300 hover:bg-white/[0.04]"
              }`}
            >
              {f.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search company or role..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-white/[0.02] border border-white/[0.05] rounded-xl pl-9 pr-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-all"
          />
        </div>
      </motion.div>

      {/* Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="glass-panel-elevated"
        style={{ overflowX: "auto" }}
      >
        <table className="premium-table">
          <thead>
            <tr>
              <th>Company & Role</th>
              <th>Location</th>
              <th>Source</th>
              <th>Match</th>
              <th style={{ minWidth: 240 }}>Action / Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="text-center py-20">
                  <Loader2 className="animate-spin text-gray-600 mx-auto" />
                </td>
              </tr>
            ) : filteredJobs.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-center py-20">
                  <p className="text-gray-500 font-medium">No jobs found matching your filters.</p>
                </td>
              </tr>
            ) : (
              filteredJobs.map(job => {
                const needsEmail = job.recruiter_email?.startsWith("needs");
                return (
                  <tr key={job.id}>
                    <td>
                      <div className="flex flex-col gap-1">
                        <span className="text-white font-semibold">{job.company}</span>
                        <div className="flex items-center gap-2">
                          {job.url ? (
                            <Link href={job.url} target="_blank" className="text-gray-400 hover:text-cyan-400 transition-colors flex items-center gap-1 text-xs">
                              <span className="truncate max-w-[200px]">{job.title}</span>
                              <ExternalLink size={10} />
                            </Link>
                          ) : (
                            <span className="text-gray-400 text-xs truncate max-w-[200px]">{job.title}</span>
                          )}
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="text-xs text-gray-400">
                        {job.location || "—"}
                      </span>
                    </td>
                    
                    <td>
                      <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
                        {job.source || "unknown"}
                      </span>
                    </td>
                    
                    <td>
                      {job.match_score != null ? (
                        <span className={`badge ${job.match_score > 0.6 ? 'badge-cyan' : 'badge-neutral'}`}>
                          {(job.match_score * 100).toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                    
                    <td>
                      {needsEmail ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="email"
                            placeholder="Email address..."
                            value={resumeEmail[job.id] || ""}
                            onChange={e => setResumeEmail({...resumeEmail, [job.id]: e.target.value})}
                            className="flex-1 bg-white/[0.03] border border-amber-500/20 rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-gray-600 focus:outline-none focus:border-cyan-500/40"
                          />
                          <button
                            onClick={() => handleResume(job.id)}
                            disabled={resuming[job.id]}
                            className="bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-50 flex items-center gap-1.5"
                          >
                            {resuming[job.id] ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                            Send
                          </button>
                        </div>
                      ) : job.status === "sent" ? (
                        <span className="badge badge-emerald"><CheckCircle2 size={12} /> Sent</span>
                      ) : job.status === "applied" ? (
                        <span className="badge badge-emerald"><CheckCircle2 size={12} /> Applied</span>
                      ) : job.status === "applying" ? (
                        <span className="badge badge-cyan"><Loader2 size={12} className="animate-spin" /> Applying</span>
                      ) : job.status === "failed" ? (
                        <div className="flex items-center gap-2">
                          <span className="badge badge-rose"><XCircle size={12} /> Failed</span>
                          {job.apply_error && (
                            <span className="text-[10px] text-rose-400 max-w-[150px] truncate" title={job.apply_error}>
                              {job.apply_error}
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 flex-wrap">
                          {job.stage ? (
                            <span className="badge badge-cyan flex items-center gap-1.5 px-2.5 py-1">
                              <Loader2 size={12} className="animate-spin" />
                              {job.stage}
                            </span>
                          ) : (
                            <span className="badge badge-violet capitalize"><Clock size={12} /> {job.status || "Queued"}</span>
                          )}
                          <div className="flex flex-col gap-1">
                            {/* Resume Mode Toggle */}
                            <button
                              onClick={() => toggleResumeMode(job.id)}
                              disabled={resuming[job.id]}
                              title={resumeMode[job.id] === "generate" ? "Click to switch to prebuilt resume" : "Click to switch to JD-matched resume"}
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border transition-all ${
                                resumeMode[job.id] === "generate"
                                  ? "bg-violet-500/15 border-violet-500/30 text-violet-300"
                                  : "bg-white/[0.04] border-white/[0.08] text-gray-500 hover:text-gray-300"
                              }`}
                            >
                              {resumeMode[job.id] === "generate" ? "✦ JD Resume" : "📄 Prebuilt"}
                            </button>
                            {/* Auto Apply Button */}
                            <button
                              onClick={() => handleAutoApply(job.id, job.url)}
                              disabled={resuming[job.id] || !job.url}
                              className="bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/20 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-50 flex items-center gap-1.5"
                            >
                              {resuming[job.id] ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} className="fill-current" />}
                              Auto Apply
                            </button>
                          </div>
                        </div>
                      )}

                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </motion.div>
    </div>
  );
}

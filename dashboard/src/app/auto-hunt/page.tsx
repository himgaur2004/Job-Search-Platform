"use client";

import { useState, useEffect, useRef } from "react";
import {
  Rocket, Clock, Zap, CheckCircle2, Activity, Play,
  Loader2, AlertCircle, Search, MapPin, RefreshCw
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const INTERVALS = [
  { label: "Manual", value: 0, desc: "Run once" },
  { label: "30m", value: 30, desc: "Aggressive" },
  { label: "1h", value: 60, desc: "Standard" },
  { label: "3h", value: 180, desc: "Relaxed" },
  { label: "6h", value: 360, desc: "Minimal" },
];

interface ScoutStatus {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  jobs_found: number;
  current_keyword: string | null;
  error: string | null;
}

function elapsed(iso: string | null): string {
  if (!iso) return "";
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

export default function AutoHuntPage() {
  const [keyword, setKeyword] = useState("Software Engineer");
  const [location, setLocation] = useState("India");
  const [experience, setExperience] = useState("0 Yrs (Freshers Only)");
  const [searchType, setSearchType] = useState("all");
  const [scheduleInterval, setScheduleInterval] = useState(0);
  const [starting, setStarting] = useState(false);
  const [status, setStatus] = useState<ScoutStatus | null>(null);
  const [tick, setTick] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const scheduleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll /api/service1/status every 3 seconds regardless of page
  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/service1/status", { cache: "no-store" });
      if (res.ok) {
        const data: ScoutStatus = await res.json();
        setStatus(data);
        setTick(t => t + 1); // force elapsed time re-render
      }
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchStatus(); // initial fetch
    intervalRef.current = setInterval(fetchStatus, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Schedule recurring runs
  useEffect(() => {
    if (scheduleRef.current) clearInterval(scheduleRef.current);
    if (scheduleInterval > 0) {
      scheduleRef.current = setInterval(() => {
        triggerRun();
      }, scheduleInterval * 60 * 1000);
    }
    return () => {
      if (scheduleRef.current) clearInterval(scheduleRef.current);
    };
  }, [scheduleInterval, keyword, location, experience, searchType]);

  const triggerRun = async () => {
    if (status?.running) return;
    setStarting(true);
    try {
      const res = await fetch("/api/service1/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, location, experience, search_type: searchType }),
      });
      if (res.ok) {
        setTimeout(fetchStatus, 500); // refresh status quickly
      }
    } catch (e) {
      console.error(e);
    } finally {
      setStarting(false);
    }
  };

  const isRunning = status?.running ?? false;
  const hasError = status?.error;

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center gap-4 border-b border-white/[0.05] pb-6"
      >
        <div className="w-12 h-12 rounded-xl bg-cyan-500/10 flex items-center justify-center">
          <Rocket className="text-cyan-400" size={24} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Job Scout</h1>
          <p className="text-sm text-gray-400 mt-1">Autonomous LinkedIn job discovery engine</p>
        </div>
      </motion.div>

      {/* Live Status Banner */}
      <AnimatePresence>
        {status && (
          <motion.div
            key="status-banner"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`rounded-xl border px-5 py-4 flex items-center gap-4 ${
              isRunning
                ? "bg-cyan-500/10 border-cyan-500/30"
                : hasError
                ? "bg-rose-500/10 border-rose-500/30"
                : status.finished_at
                ? "bg-emerald-500/10 border-emerald-500/20"
                : "bg-white/[0.03] border-white/[0.06]"
            }`}
          >
            {isRunning ? (
              <Loader2 className="animate-spin text-cyan-400 shrink-0" size={20} />
            ) : hasError ? (
              <AlertCircle className="text-rose-400 shrink-0" size={20} />
            ) : status.finished_at ? (
              <CheckCircle2 className="text-emerald-400 shrink-0" size={20} />
            ) : (
              <Activity className="text-gray-500 shrink-0" size={20} />
            )}

            <div className="flex-1 min-w-0">
              {isRunning ? (
                <>
                  <p className="text-sm font-semibold text-cyan-300">Scout Running…</p>
                  <p className="text-xs text-cyan-400/60 mt-0.5">
                    {status.current_keyword
                      ? `Searching: ${status.current_keyword}`
                      : "Initializing…"}
                    {status.started_at && ` · ${elapsed(status.started_at)} elapsed`}
                  </p>
                </>
              ) : hasError ? (
                <>
                  <p className="text-sm font-semibold text-rose-300">Scout Error</p>
                  <p className="text-xs text-rose-400/60 mt-0.5 truncate">{status.error}</p>
                </>
              ) : status.finished_at ? (
                <>
                  <p className="text-sm font-semibold text-emerald-300">
                    Scout Complete · {status.jobs_found} jobs found
                  </p>
                  <p className="text-xs text-emerald-400/50 mt-0.5">
                    Finished {elapsed(status.finished_at)} ago
                  </p>
                </>
              ) : (
                <p className="text-sm text-gray-500">Scout idle — ready to run</p>
              )}
            </div>

            {isRunning && (
              <div className="flex gap-1 shrink-0">
                {[0, 1, 2].map(i => (
                  <motion.div
                    key={i}
                    animate={{ scaleY: [1, 2, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
                    className="w-1 h-4 bg-cyan-400/60 rounded-full"
                  />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Config Panel */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="glass-panel-elevated p-8 space-y-8 relative overflow-hidden"
      >
        <div className="absolute -top-20 -right-20 w-64 h-64 bg-cyan-500/10 rounded-full blur-[80px] pointer-events-none" />

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="input-label flex items-center gap-1.5">
              <Search size={11} /> Target Role(s)
            </label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="input-field font-medium"
              placeholder="e.g. SDE, Frontend"
              disabled={isRunning}
            />
            <p className="text-[10px] text-gray-500 mt-1 ml-1">Comma separate for multiple</p>
          </div>
          <div>
            <label className="input-label flex items-center gap-1.5">
              <MapPin size={11} /> Location
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="input-field font-medium"
              placeholder="e.g. India, Remote"
              disabled={isRunning}
            />
          </div>
          <div>
            <label className="input-label flex items-center gap-1.5">
              <Zap size={11} /> Max Exp (Years)
            </label>
            <div className="flex gap-2">
              <input
                type="number"
                min={0}
                max={20}
                value={experience === "Any" ? "" : experience.replace(/[^0-9]/g, "") || "0"}
                onChange={(e) => {
                  const val = e.target.value;
                  setExperience(val === "" ? "Any" : `${val} Yrs Max`);
                }}
                placeholder="0 = Freshers"
                className="input-field font-medium bg-black/40 text-white w-full"
                disabled={isRunning}
              />
              <select
                value={experience}
                onChange={(e) => setExperience(e.target.value)}
                className="input-field font-medium bg-black/40 text-white appearance-none text-xs w-28 shrink-0"
                disabled={isRunning}
              >
                <option value="0 Yrs (Freshers Only)">0 Yrs (Freshers)</option>
                <option value="1 Yr Max">1 Yr Max</option>
                <option value="2 Yrs Max">2 Yrs Max</option>
                <option value="3 Yrs Max">3 Yrs Max</option>
                <option value="5 Yrs Max">5 Yrs Max</option>
                <option value="Any">Any Exp</option>
              </select>
            </div>
          </div>
          <div>
            <label className="input-label flex items-center gap-1.5">
              <Zap size={11} /> Search Target
            </label>
            <select
              value={searchType}
              onChange={(e) => setSearchType(e.target.value)}
              className="input-field font-medium bg-black/40 text-white appearance-none"
              disabled={isRunning}
            >
              <option value="all">All Sources</option>
              <option value="job_boards">Job Boards Only</option>
              <option value="ats">Company ATS Only</option>
            </select>
          </div>
        </div>

        <div className="pt-4 border-t border-white/[0.05]">
          <label className="input-label flex items-center gap-2 mb-4">
            <Clock size={12} /> Auto-Repeat Schedule
          </label>
          <div className="grid grid-cols-5 gap-3">
            {INTERVALS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setScheduleInterval(opt.value)}
                className={`relative rounded-xl p-3 text-center transition-all duration-200 border ${
                  scheduleInterval === opt.value
                    ? "bg-cyan-500/10 border-cyan-500/30 shadow-[0_0_15px_rgba(0,212,255,0.1)]"
                    : "bg-white/[0.02] border-white/[0.05] hover:border-white/[0.1]"
                }`}
              >
                {scheduleInterval === opt.value && (
                  <motion.div
                    layoutId="scheduleIndicator"
                    className="absolute -top-px left-1/2 -translate-x-1/2 w-8 h-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(0,212,255,1)]"
                  />
                )}
                <div className={`text-sm font-bold ${scheduleInterval === opt.value ? "text-cyan-300" : "text-gray-400"}`}>
                  {opt.label}
                </div>
                <div className={`text-[10px] mt-1 ${scheduleInterval === opt.value ? "text-cyan-400/60" : "text-gray-600"}`}>
                  {opt.desc}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="pt-6 border-t border-white/[0.05] flex items-center justify-between gap-4">
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <Zap size={12} className="text-cyan-500/50" />
            Searches up to 50 jobs · Auto-stores in DB · No auth needed
          </div>
          <button
            onClick={triggerRun}
            disabled={starting || isRunning || !keyword}
            className="btn-primary min-w-[140px] flex items-center justify-center gap-2"
          >
            {starting ? (
              <Loader2 size={16} className="animate-spin" />
            ) : isRunning ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : (
              <Play size={16} className="fill-current" />
            )}
            {isRunning ? "Running…" : starting ? "Starting…" : "Run Scout"}
          </button>
        </div>
      </motion.div>

      {/* Multi-Agent Crawler Network Panel */}
      <CrawlerNetworkPanel />
    </div>
  );
}

function CrawlerNetworkPanel() {
  const [stats, setStats] = useState<any>(null);
  const [cStatus, setCStatus] = useState<any>(null);
  const [triggering, setTriggering] = useState(false);

  const fetchStats = async () => {
    try {
      const res1 = await fetch("/api/crawler/stats");
      if (res1.ok) setStats(await res1.json());
      const res2 = await fetch("/api/crawler/status");
      if (res2.ok) setCStatus(await res2.json());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchStats();
    const timer = setInterval(fetchStats, 5000);
    return () => clearInterval(timer);
  }, []);

  const triggerCrawler = async () => {
    setTriggering(true);
    try {
      await fetch("/api/crawler/run", { method: "POST" });
      setTimeout(fetchStats, 1000);
    } catch { /* ignore */ }
    finally { setTriggering(false); }
  };

  if (!stats) return null;

  const isCrawlerRunning = cStatus?.running;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="glass-panel p-6 space-y-6 relative overflow-hidden border border-cyan-500/20"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Activity className="text-cyan-400" size={18} />
            Multi-Agent Discovery Engine
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Background worker crawling 13,700+ company career pages & ATS portals
          </p>
        </div>
        <button
          onClick={triggerCrawler}
          disabled={triggering || isCrawlerRunning}
          className="px-4 py-2 rounded-xl text-xs font-semibold bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/20 transition-all flex items-center gap-2"
        >
          {isCrawlerRunning ? (
            <>
              <Loader2 size={14} className="animate-spin text-cyan-400" />
              Crawling Engine Active…
            </>
          ) : (
            <>
              <RefreshCw size={14} />
              Run Pipeline Now
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
          <div className="text-2xl font-extrabold text-cyan-400">
            {stats.total_jobs?.toLocaleString() || "0"}
          </div>
          <div className="text-xs text-gray-400 mt-1 font-medium">Total Indexed Jobs</div>
        </div>

        <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
          <div className="text-2xl font-extrabold text-emerald-400">
            {stats.total_ats_companies?.toLocaleString() || "0"}
          </div>
          <div className="text-xs text-gray-400 mt-1 font-medium">ATS Companies (6 APIs)</div>
        </div>

        <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
          <div className="text-2xl font-extrabold text-amber-400">
            {stats.custom_active_career_pages || "0"}
          </div>
          <div className="text-xs text-gray-400 mt-1 font-medium">Custom Startup Pages</div>
        </div>

        <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
          <div className="text-2xl font-extrabold text-purple-400">
            {stats.india_jobs?.toLocaleString() || "0"}
          </div>
          <div className="text-xs text-gray-400 mt-1 font-medium">India Hub Jobs</div>
        </div>
      </div>

      <div className="text-[11px] text-gray-500 flex items-center justify-between border-t border-white/[0.05] pt-4">
        <span>Auto-runs every 6 hours · Playwright Chromium + Groq LLM + FTS5 SQLite</span>
        <span className="text-cyan-400/70">
          Greenhouse, Lever, Workday, Ashby, Workable, BambooHR, Custom LLM
        </span>
      </div>
    </motion.div>
  );
}

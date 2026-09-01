"use client";

import { useState, useEffect } from "react";
import { FileText, Plus, Save, Trash2, Star, Loader2, Code2 } from "lucide-react";
import { motion } from "framer-motion";

type Resume = { id: number; name: string; latex_content: string; is_active: number; };

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedResume, setSelectedResume] = useState<Resume | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [latexContent, setLatexContent] = useState("");
  const [isActive, setIsActive] = useState(false);

  const fetchResumes = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/resumes");
      const data = await res.json();
      setResumes(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchResumes(); }, []);

  const handleCreateNew = () => {
    setSelectedResume(null);
    setName("Untitled Resume");
    setLatexContent("\\documentclass{article}\n\\begin{document}\n\n\\end{document}");
    setIsActive(false);
    setIsEditing(true);
  };

  const handleEdit = (r: Resume) => {
    setSelectedResume(r);
    setName(r.name);
    setLatexContent(r.latex_content);
    setIsActive(r.is_active === 1);
    setIsEditing(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this resume?")) return;
    await fetch(`/api/resumes/${id}`, { method: "DELETE" });
    if (selectedResume?.id === id) setIsEditing(false);
    fetchResumes();
  };

  const handleSave = async () => {
    setSaving(true);
    const payload = { name, latex_content: latexContent, is_active: isActive };
    if (selectedResume) {
      await fetch(`/api/resumes/${selectedResume.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await fetch("/api/resumes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    setSaving(false);
    setIsEditing(false);
    fetchResumes();
  };

  const handleSetActive = async (r: Resume) => {
    await fetch(`/api/resumes/${r.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: r.name, latex_content: r.latex_content, is_active: true }),
    });
    fetchResumes();
  };

  return (
    <div className="space-y-8 h-[calc(100vh-6rem)] flex flex-col">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center justify-between border-b border-white/[0.05] pb-6 shrink-0"
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
            <Code2 className="text-emerald-400" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">LaTeX Resumes</h1>
            <p className="text-sm text-gray-400 mt-1">Manage dynamic resume templates</p>
          </div>
        </div>
        <button onClick={handleCreateNew} className="btn-primary py-2.5 px-4 rounded-xl text-sm" style={{ background: "linear-gradient(135deg, #10b981 0%, #059669 100%)", boxShadow: "0 4px 16px rgba(16,185,129,0.2)" }}>
          <Plus size={16} /> New Resume
        </button>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-0"
      >
        {/* Sidebar */}
        <div className="glass-panel p-4 flex flex-col gap-2 overflow-y-auto custom-scrollbar lg:col-span-1">
          {loading ? (
            <div className="flex justify-center py-10"><Loader2 className="animate-spin text-gray-600" /></div>
          ) : resumes.length === 0 ? (
            <p className="text-center text-sm text-gray-600 py-10">No resumes found.</p>
          ) : (
            resumes.map(r => (
              <div
                key={r.id}
                onClick={() => handleEdit(r)}
                className={`p-4 rounded-xl border transition-all cursor-pointer group flex flex-col gap-3 ${
                  selectedResume?.id === r.id
                    ? "bg-emerald-500/10 border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.1)]"
                    : "bg-white/[0.02] border-white/[0.05] hover:border-white/[0.1]"
                }`}
              >
                <div className="flex justify-between items-start">
                  <h3 className="font-semibold text-white text-sm truncate pr-2">{r.name}</h3>
                  {r.is_active === 1 && <Star className="text-amber-400 fill-amber-400 shrink-0" size={14} />}
                </div>
                
                <div className="flex justify-between items-center mt-auto">
                  {r.is_active === 0 ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleSetActive(r); }}
                      className="text-[10px] uppercase font-bold tracking-wider text-gray-500 hover:text-emerald-400 transition-colors"
                    >
                      Set Active
                    </button>
                  ) : (
                    <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">Active</span>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(r.id); }}
                    className="text-gray-600 hover:text-rose-400 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Editor */}
        <div className="lg:col-span-3 glass-panel-elevated rounded-2xl flex flex-col overflow-hidden relative">
          {/* Glow */}
          <div className="absolute -top-32 -right-32 w-80 h-80 bg-emerald-500/10 rounded-full blur-[100px] pointer-events-none" />

          {isEditing ? (
            <>
              <div className="flex items-center justify-between p-4 border-b border-white/[0.05] bg-white/[0.01]">
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="bg-transparent text-lg font-bold text-white focus:outline-none placeholder:text-gray-600 flex-1"
                  placeholder="Resume Name"
                />
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-xs font-semibold text-gray-400 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={isActive}
                      onChange={(e) => setIsActive(e.target.checked)}
                      className="rounded bg-black/50 border-white/20 text-emerald-500 focus:ring-emerald-500 w-4 h-4"
                    />
                    SET ACTIVE
                  </label>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all disabled:opacity-50 flex items-center gap-2"
                  >
                    {saving ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />}
                    Save
                  </button>
                </div>
              </div>

              <div className="flex-1 relative bg-black/40">
                <textarea
                  value={latexContent}
                  onChange={(e) => setLatexContent(e.target.value)}
                  className="absolute inset-0 w-full h-full bg-transparent p-6 text-emerald-50 font-mono text-sm leading-relaxed resize-none focus:outline-none custom-scrollbar"
                  spellCheck={false}
                  placeholder="% Paste LaTeX code here..."
                />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <FileText size={32} className="text-gray-600 mb-4" />
              <h3 className="text-white font-medium">No resume selected</h3>
              <p className="text-gray-500 text-sm mt-1">Select a template from the sidebar to edit.</p>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

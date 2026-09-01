"use client";

import { useState, useEffect } from "react";
import { Mail, Plus, Save, Trash2, Star, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { fetchTemplates, createTemplate, updateTemplate, deleteTemplate } from "@/lib/api";
import { Template } from "@/lib/types";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [subjectTemplate, setSubjectTemplate] = useState("");
  const [bodyTemplate, setBodyTemplate] = useState("");
  const [isActive, setIsActive] = useState(false);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await fetchTemplates();
      setTemplates(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { loadTemplates(); }, []);

  const handleCreateNew = () => {
    setSelectedTemplate(null);
    setName("Untitled Template");
    setSubjectTemplate("Application for {{company}}");
    setBodyTemplate("Hi {{recruiter_name}},\n\nI saw the opening at {{company}} and believe I would be a great fit because...\n\nThanks,\nMy Name");
    setIsActive(false);
    setIsEditing(true);
  };

  const handleEdit = (t: Template) => {
    setSelectedTemplate(t);
    setName(t.name);
    setSubjectTemplate(t.subject_template);
    setBodyTemplate(t.body_template);
    setIsActive(t.is_active);
    setIsEditing(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this template?")) return;
    await deleteTemplate(id);
    if (selectedTemplate?.id === id) setIsEditing(false);
    loadTemplates();
  };

  const handleSave = async () => {
    setSaving(true);
    const payload = { name, subject_template: subjectTemplate, body_template: bodyTemplate, is_active: isActive };
    if (selectedTemplate) {
      await updateTemplate(selectedTemplate.id, payload);
    } else {
      await createTemplate(payload);
    }
    setSaving(false);
    setIsEditing(false);
    loadTemplates();
  };

  const handleSetActive = async (t: Template) => {
    await updateTemplate(t.id, { name: t.name, subject_template: t.subject_template, body_template: t.body_template, is_active: true });
    loadTemplates();
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
          <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center">
            <Mail className="text-orange-400" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Email Templates</h1>
            <p className="text-sm text-gray-400 mt-1">Manage AI outreach templates</p>
          </div>
        </div>
        <button onClick={handleCreateNew} className="btn-primary py-2.5 px-4 rounded-xl text-sm" style={{ background: "linear-gradient(135deg, #f97316 0%, #ea580c 100%)", boxShadow: "0 4px 16px rgba(249,115,22,0.2)" }}>
          <Plus size={16} /> New Template
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
          ) : templates.length === 0 ? (
            <p className="text-center text-sm text-gray-600 py-10">No templates found.</p>
          ) : (
            templates.map(t => (
              <div
                key={t.id}
                onClick={() => handleEdit(t)}
                className={`p-4 rounded-xl border transition-all cursor-pointer group flex flex-col gap-3 ${
                  selectedTemplate?.id === t.id
                    ? "bg-orange-500/10 border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.1)]"
                    : "bg-white/[0.02] border-white/[0.05] hover:border-white/[0.1]"
                }`}
              >
                <div className="flex justify-between items-start">
                  <h3 className="font-semibold text-white text-sm truncate pr-2">{t.name}</h3>
                  {t.is_active && <Star className="text-amber-400 fill-amber-400 shrink-0" size={14} />}
                </div>
                
                <div className="flex justify-between items-center mt-auto">
                  {!t.is_active ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleSetActive(t); }}
                      className="text-[10px] uppercase font-bold tracking-wider text-gray-500 hover:text-orange-400 transition-colors"
                    >
                      Set Active
                    </button>
                  ) : (
                    <span className="text-[10px] uppercase font-bold tracking-wider text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded">Active</span>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(t.id); }}
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
          <div className="absolute -top-32 -right-32 w-80 h-80 bg-orange-500/10 rounded-full blur-[100px] pointer-events-none" />

          {isEditing ? (
            <>
              <div className="flex items-center justify-between p-4 border-b border-white/[0.05] bg-white/[0.01] shrink-0">
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="bg-transparent text-lg font-bold text-white focus:outline-none placeholder:text-gray-600 flex-1"
                  placeholder="Template Name"
                />
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-xs font-semibold text-gray-400 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={isActive}
                      onChange={(e) => setIsActive(e.target.checked)}
                      className="rounded bg-black/50 border-white/20 text-orange-500 focus:ring-orange-500 w-4 h-4"
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

              <div className="flex flex-col flex-1 p-6 gap-4 overflow-y-auto custom-scrollbar">
                <div className="flex flex-col gap-2 shrink-0">
                  <label className="input-label mb-0">Subject Template</label>
                  <input
                    type="text"
                    value={subjectTemplate}
                    onChange={(e) => setSubjectTemplate(e.target.value)}
                    className="input-field font-mono text-sm"
                    placeholder="e.g. Application for {{company}}"
                  />
                </div>
                
                <div className="flex flex-col gap-2 flex-1 min-h-[300px]">
                  <div className="flex justify-between items-center">
                    <label className="input-label mb-0">Body Template</label>
                    <span className="text-xs text-gray-500">Variables: {'{{company}}, {{recruiter_name}}, {{jd_text}}'}</span>
                  </div>
                  <textarea
                    value={bodyTemplate}
                    onChange={(e) => setBodyTemplate(e.target.value)}
                    className="input-field flex-1 font-mono text-sm leading-relaxed resize-none h-full"
                    spellCheck={false}
                    placeholder="Write your email body template here..."
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Mail size={32} className="text-gray-600 mb-4" />
              <h3 className="text-white font-medium">No template selected</h3>
              <p className="text-gray-500 text-sm mt-1">Select a template from the sidebar to edit.</p>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Plus,
  Copy,
  Trash2,
  Pencil,
  ArrowRight,
  Video,
  Clock,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { CharacterRecord, Project, VideoExport } from "@/lib/types";

interface ProjectSummary {
  project: Project;
  latestExport?: VideoExport;
  character?: CharacterRecord;
}

export default function DashboardPage() {
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [targetDuration, setTargetDuration] = useState(120);
  const [computeMode, setComputeMode] = useState<"local_hybrid" | "local_only" | "cloud_preferred">("local_hybrid");
  const [saving, setSaving] = useState(false);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const projects = await api.listProjects();
      const enriched = await Promise.all(
        projects.map(async (project) => {
          const [exportsList, chars] = await Promise.all([
            api.listExports(project.id).catch(() => []),
            api.listCharacters(project.id).catch(() => []),
          ]);
          return {
            project,
            latestExport: exportsList[0],
            character: chars[0],
          };
        }),
      );
      setItems(enriched);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const openCreate = () => {
    setEditing(null);
    setTitle("");
    setDescription("");
    setTargetDuration(120);
    setComputeMode("local_hybrid");
    setShowCreate(true);
  };

  const openEdit = (p: Project) => {
    setEditing(p);
    setTitle(p.title);
    setDescription(p.description || "");
    setTargetDuration(p.target_duration_sec);
    setComputeMode(p.compute_mode);
    setShowCreate(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        await api.updateProject(editing.id, {
          title,
          description: description || null,
          target_duration_sec: targetDuration,
          compute_mode: computeMode,
        });
      } else {
        await api.createProject({
          title,
          description: description || undefined,
          target_duration_sec: targetDuration,
          compute_mode: computeMode,
        });
      }
      setShowCreate(false);
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save project");
    } finally {
      setSaving(false);
    }
  };

  const handleDuplicate = async (id: string) => {
    try {
      await api.duplicateProject(id);
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duplicate failed");
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete project "${name}" and all its generated assets?`)) return;
    try {
      await api.deleteProject(id);
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Educational Video Projects
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Create, customize, and export 1080×1920 vertical split-screen videos from your script, character, and voice.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Video Project
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center rounded-2xl border border-slate-200 bg-white py-20 text-slate-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-blue-600" />
          Loading projects...
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <Video className="mx-auto h-10 w-10 text-slate-400" />
          <h2 className="mt-3 text-base font-semibold text-slate-900">No video projects yet</h2>
          <p className="mt-1 text-sm text-slate-500">
            Start a new project to write a script, upload a character, and generate your first vertical video.
          </p>
          <button
            onClick={openCreate}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            Create First Project
          </button>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(({ project, latestExport, character }) => (
            <div
              key={project.id}
              className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-300"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    {character ? (
                      <img
                        src={api.characterPreviewUrl(character.id)}
                        alt={character.name}
                        className="h-12 w-12 rounded-xl border border-slate-200 object-cover"
                      />
                    ) : (
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
                        <Video className="h-5 w-5" />
                      </div>
                    )}
                    <div>
                      <h3 className="font-bold text-slate-900 line-clamp-1">{project.title}</h3>
                      <p className="text-xs text-slate-500">
                        {project.resolution} • {project.compute_mode}
                      </p>
                    </div>
                  </div>
                </div>

                {project.description && (
                  <p className="mt-3 text-xs text-slate-600 line-clamp-2">{project.description}</p>
                )}

                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                    <Clock className="h-3 w-3" />
                    {project.target_duration_sec}s target
                  </span>
                  {latestExport ? (
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-medium ${
                        latestExport.status === "completed"
                          ? "bg-emerald-50 text-emerald-700"
                          : latestExport.status === "failed"
                            ? "bg-red-50 text-red-700"
                            : "bg-blue-50 text-blue-700"
                      }`}
                    >
                      {latestExport.status === "completed" && <CheckCircle2 className="h-3 w-3" />}
                      Export: {latestExport.status}
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-500">
                      Not exported
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-3">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => openEdit(project)}
                    className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                    title="Edit project"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDuplicate(project.id)}
                    className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                    title="Duplicate project"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(project.id, project.title)}
                    className="rounded-lg p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-600"
                    title="Delete project"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <Link
                  href={`/projects/${project.id}`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-600"
                >
                  Open Studio
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <form onSubmit={handleSave} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold text-slate-900">
              {editing ? "Edit Project" : "New Video Project"}
            </h2>
            <div className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Title</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. How Neural Networks Learn"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700">
                    Target Duration (sec)
                  </label>
                  <input
                    type="number"
                    min={10}
                    max={1800}
                    value={targetDuration}
                    onChange={(e) => setTargetDuration(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700">Compute Mode</label>
                  <select
                    value={computeMode}
                    onChange={(e) =>
                      setComputeMode(e.target.value as "local_hybrid" | "local_only" | "cloud_preferred")
                    }
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  >
                    <option value="local_hybrid">Local Hybrid (6GB Safe)</option>
                    <option value="local_only">Local Only</option>
                    <option value="cloud_preferred">Cloud Preferred</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                {editing ? "Save Changes" : "Create Project"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

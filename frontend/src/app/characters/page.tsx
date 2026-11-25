"use client";

import { useEffect, useState } from "react";
import { Users, Plus, Trash2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { FlowCharacter } from "@/lib/types";

export default function CharactersPage() {
  const [characters, setCharacters] = useState<FlowCharacter[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [appearancePrompt, setAppearancePrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setCharacters(await api.listFlowCharacters().catch(() => []));
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createFlowCharacter(name, description, appearancePrompt, file);
      setName("");
      setDescription("");
      setAppearancePrompt("");
      setFile(null);
      await load();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <Users className="h-6 w-6 text-blue-600" />
          My Characters
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Create reusable character references from text descriptions or photos to maintain consistent faces and clothing across scenes.
        </p>
      </div>

      <form onSubmit={handleCreate} className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 sm:grid-cols-2">
        <div>
          <label className="block text-xs font-semibold text-slate-700">Character Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Dr. Elena Vance"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            required
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-700">Reference Photo (Optional)</label>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-1 w-full text-xs text-slate-600"
          />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-xs font-semibold text-slate-700">
            Appearance Consistency Prompt
          </label>
          <input
            value={appearancePrompt}
            onChange={(e) => setAppearancePrompt(e.target.value)}
            placeholder="e.g. woman in her 30s, dark curly hair, silver-blue futuristic flight suit"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            required
          />
        </div>
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Save Character
          </button>
        </div>
      </form>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {characters.map((ch) => (
          <div key={ch.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            {ch.reference_image_path && (
              <img
                src={api.flowCharacterImageUrl(ch.id)}
                alt={ch.name}
                className="mb-3 h-40 w-full rounded-xl object-cover"
              />
            )}
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-bold text-slate-900">{ch.name}</h3>
                <p className="mt-1 text-xs text-slate-600">{ch.appearance_prompt}</p>
              </div>
              <button
                onClick={async () => {
                  await api.deleteFlowCharacter(ch.id);
                  await load();
                }}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
                title="Delete character"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

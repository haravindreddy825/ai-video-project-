"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Film,
  GitBranch,
  History,
  Image as ImageIcon,
  Loader2,
  Music,
  Play,
  Plus,
  Sparkles,
  Users,
  Wand2,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  FlowCharacter,
  FlowProject,
  FlowProviderCapability,
  VoicePreset,
} from "@/lib/types";

function FlowStudioInner() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get("prompt") || "";

  const [providers, setProviders] = useState<FlowProviderCapability[]>([]);
  const [characters, setCharacters] = useState<FlowCharacter[]>([]);
  const [voices, setVoices] = useState<VoicePreset[]>([]);
  const [projects, setProjects] = useState<FlowProject[]>([]);
  const [activeProject, setActiveProject] = useState<FlowProject | null>(null);

  const [title, setTitle] = useState("Cinematic 2-Minute AI Film");
  const [prompt, setPrompt] = useState(
    initialPrompt ||
      "A lone astronaut discovers an ancient glowing library buried beneath the ice of Europa. As she brushes frost from the crystal shelves, holographic star maps awaken and guide her toward a hidden portal.",
  );
  const [aspectRatio, setAspectRatio] = useState<"16:9" | "9:16" | "1:1">("16:9");
  const [durationSec, setDurationSec] = useState<30 | 60 | 90 | 120>(120);
  const [visualStyle, setVisualStyle] = useState("cinematic");
  const [quality, setQuality] = useState<"lite" | "fast" | "standard">("lite");
  const [providerId, setProviderId] = useState<"veo_3_1" | "comfyui_wan2_1">("veo_3_1");
  const [voiceId, setVoiceId] = useState("af_heart");
  const [selectedCharIds, setSelectedCharIds] = useState<string[]>([]);
  const [includeSubtitles, setIncludeSubtitles] = useState(true);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadWorkspace = async (selectId?: string) => {
    try {
      const [provs, chars, vox, projs] = await Promise.all([
        api.listFlowProviders(),
        api.listFlowCharacters(),
        api.listVoices(),
        api.listFlowProjects(),
      ]);
      setProviders(provs);
      setCharacters(chars);
      setVoices(vox);
      setProjects(projs);

      const targetId = selectId || activeProject?.id || projs[0]?.id;
      if (targetId) {
        const detail = await api.getFlowProject(targetId);
        setActiveProject(detail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Flow workspace");
    }
  };

  useEffect(() => {
    loadWorkspace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedProvider = providers.find((p) => p.id === providerId);

  const handleCreateStoryboard = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("storyboard");
    setError(null);
    setNotice(null);
    try {
      const created = await api.createFlowProject({
        title,
        prompt,
        aspect_ratio: aspectRatio,
        target_duration_sec: durationSec,
        visual_style: visualStyle,
        quality,
        provider: providerId,
        voice_id: voiceId,
        character_ids: selectedCharIds,
      });
      setActiveProject(created);
      setNotice(
        `Storyboard created with ${created.scenes?.length || 0} continuous scenes (${durationSec}s target).`,
      );
      await loadWorkspace(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create storyboard");
    } finally {
      setBusy(null);
    }
  };

  const handleGenerateScene = async (sceneId: string) => {
    setBusy(`gen-${sceneId}`);
    setError(null);
    setNotice(null);
    try {
      await api.generateFlowScene(sceneId);
      setNotice("Scene clip generated and saved.");
      if (activeProject) await loadWorkspace(activeProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scene generation failed");
    } finally {
      setBusy(null);
    }
  };

  const handleVariations = async (sceneId: string) => {
    setBusy(`var-${sceneId}`);
    setError(null);
    try {
      await api.createSceneVariations(sceneId, 2);
      setNotice("Created 2 scene variations.");
      if (activeProject) await loadWorkspace(activeProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create variations");
    } finally {
      setBusy(null);
    }
  };

  const handleExtendScene = async (sceneId: string) => {
    setBusy(`ext-${sceneId}`);
    setError(null);
    try {
      await api.extendFlowScene(sceneId, "Continue the shot smoothly with cinematic motion.");
      setNotice("Extended clip added to storyboard.");
      if (activeProject) await loadWorkspace(activeProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extension failed");
    } finally {
      setBusy(null);
    }
  };

  const handleAssemble = async () => {
    if (!activeProject) return;
    setBusy("assemble");
    setError(null);
    setNotice(null);
    try {
      const res = await api.assembleFlowProject(activeProject.id, includeSubtitles);
      setNotice(`Assembled final ${res.duration_sec}s MP4 with narration & captions.`);
      await loadWorkspace(activeProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assembly failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            <Wand2 className="h-6 w-6 text-blue-600" />
            Flow Studio — 2-Minute AI Video Workspace
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Describe any story in natural language, generate an automatic multi-scene storyboard, attach consistent characters &amp; voice, and assemble up to 120s MP4.
          </p>
        </div>
        {projects.length > 0 && (
          <select
            value={activeProject?.id || ""}
            onChange={(e) => loadWorkspace(e.target.value)}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title} ({p.target_duration_sec}s • {p.aspect_ratio})
              </option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {/* Natural Language Prompt + Controls */}
      <form
        onSubmit={handleCreateStoryboard}
        className="grid gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:grid-cols-3"
      >
        <div className="space-y-4 lg:col-span-2">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide text-slate-500">
              Project Title
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 px-3.5 py-2 text-sm font-medium"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide text-slate-500">
              Natural-Language Video Prompt
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={5}
              placeholder="Describe the story, scenes, mood, characters, and pacing..."
              className="mt-1 w-full rounded-xl border border-slate-300 p-3.5 text-sm leading-relaxed focus:border-blue-500 focus:outline-none"
              required
            />
          </div>

          {/* Reusable Character Chips */}
          <div>
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">
              <Users className="h-3.5 w-3.5" />
              Consistent Characters ({selectedCharIds.length} selected)
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {characters.length === 0 ? (
                <span className="text-xs text-slate-400">
                  No saved characters yet — create reusable characters in My Characters.
                </span>
              ) : (
                characters.map((ch) => {
                  const selected = selectedCharIds.includes(ch.id);
                  return (
                    <button
                      type="button"
                      key={ch.id}
                      onClick={() =>
                        setSelectedCharIds((prev) =>
                          selected ? prev.filter((x) => x !== ch.id) : [...prev, ch.id],
                        )
                      }
                      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition ${
                        selected
                          ? "border-blue-600 bg-blue-50 text-blue-700"
                          : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      {ch.name}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>

        <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700">Duration</label>
              <select
                value={durationSec}
                onChange={(e) => setDurationSec(Number(e.target.value) as 30 | 60 | 90 | 120)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-semibold"
              >
                <option value={30}>30 Seconds</option>
                <option value={60}>60 Seconds</option>
                <option value={90}>90 Seconds</option>
                <option value={120}>120 Seconds (2 Min)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700">Aspect Ratio</label>
              <select
                value={aspectRatio}
                onChange={(e) => setAspectRatio(e.target.value as "16:9" | "9:16" | "1:1")}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-semibold"
              >
                <option value="16:9">16:9 Widescreen</option>
                <option value="9:16">9:16 Vertical</option>
                <option value="1:1">1:1 Square</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700">Visual Style</label>
              <select
                value={visualStyle}
                onChange={(e) => setVisualStyle(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-semibold"
              >
                <option value="cinematic">Cinematic Film</option>
                <option value="3d_animation">3D Animation</option>
                <option value="documentary">Documentary</option>
                <option value="anime">Anime</option>
                <option value="photorealistic">Photorealistic</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700">Quality Tier</label>
              <select
                value={quality}
                onChange={(e) => setQuality(e.target.value as "lite" | "fast" | "standard")}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-semibold"
              >
                <option value="lite">Lite ($0.05/s)</option>
                <option value="fast">Fast ($0.10/s)</option>
                <option value="standard">Standard ($0.40/s)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Video Model Provider</label>
            <select
              value={providerId}
              onChange={(e) => setProviderId(e.target.value as "veo_3_1" | "comfyui_wan2_1")}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-semibold"
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.available ? "Ready" : "Needs Setup"}
                </option>
              ))}
            </select>
            {selectedProvider && (
              <p className="mt-1 text-[11px] text-slate-600">{selectedProvider.reason}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Narration Voice</label>
            <select
              value={voiceId}
              onChange={(e) => setVoiceId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-semibold"
            >
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={busy === "storyboard"}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {busy === "storyboard" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            Generate Automatic Storyboard
          </button>
        </div>
      </form>

      {/* Active Project Storyboard & Timeline Assembly */}
      {activeProject && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Storyboard: {activeProject.title} ({activeProject.scenes?.length || 0} scenes •{" "}
                {activeProject.target_duration_sec}s)
              </h2>
              <p className="text-xs text-slate-500">
                Provider: {activeProject.provider} • Style: {activeProject.visual_style} • Aspect:{" "}
                {activeProject.aspect_ratio}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={includeSubtitles}
                  onChange={(e) => setIncludeSubtitles(e.target.checked)}
                />
                Subtitles
              </label>
              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                <Music className="h-3.5 w-3.5 text-blue-600" />
                Upload BGM
                <input
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    await api.uploadFlowMedia(activeProject.id, "bgm", f);
                    setNotice("Background music attached.");
                  }}
                />
              </label>
              <button
                onClick={handleAssemble}
                disabled={busy === "assemble"}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {busy === "assemble" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Film className="h-3.5 w-3.5" />
                )}
                Assemble Final MP4
              </button>
            </div>
          </div>

          {activeProject.final_mp4_path && (
            <div className="rounded-2xl border border-emerald-200 bg-white p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900">
                  Final Assembled Video ({activeProject.duration_sec}s)
                </h3>
                <a
                  href={api.flowFinalDownloadUrl(activeProject.id)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white"
                >
                  <Download className="h-3.5 w-3.5" />
                  Download MP4
                </a>
              </div>
              <video
                controls
                src={api.flowFinalPreviewUrl(activeProject.id)}
                className="mt-3 max-h-[420px] w-full rounded-xl bg-black"
              />
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {(activeProject.scenes || []).map((sc) => (
              <div
                key={sc.id}
                className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-900">
                      Scene {sc.order_index + 1} (v{sc.version}
                      {sc.variation_index > 1 ? ` • var ${sc.variation_index}` : ""})
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                      {sc.duration_sec}s • {sc.status}
                    </span>
                  </div>

                  {sc.video_clip_path ? (
                    <video
                      controls
                      src={api.flowScenePreviewUrl(sc.id)}
                      className="aspect-video w-full rounded-xl bg-black"
                    />
                  ) : (
                    <div className="flex aspect-video w-full items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-xs text-slate-400">
                      <Play className="mr-1.5 h-4 w-4" />
                      Clip not generated yet
                    </div>
                  )}

                  <textarea
                    defaultValue={sc.scene_prompt}
                    rows={3}
                    onBlur={(e) => {
                      if (e.target.value !== sc.scene_prompt) {
                        api.updateFlowScene(sc.id, { scene_prompt: e.target.value });
                      }
                    }}
                    className="w-full rounded-lg border border-slate-200 p-2 text-xs text-slate-700"
                  />

                  {sc.error_message && (
                    <p className="rounded-lg bg-red-50 p-2 text-[11px] text-red-700">
                      {sc.error_message}
                    </p>
                  )}
                </div>

                <div className="mt-3 flex flex-wrap items-center justify-between gap-1.5 border-t border-slate-100 pt-3 text-xs">
                  <button
                    onClick={() => handleGenerateScene(sc.id)}
                    disabled={busy === `gen-${sc.id}`}
                    className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1 font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {busy === `gen-${sc.id}` ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Sparkles className="h-3 w-3" />
                    )}
                    {sc.video_clip_path ? "Regenerate" : "Generate"}
                  </button>

                  <label className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 font-medium text-slate-700 hover:bg-slate-50">
                    <ImageIcon className="h-3 w-3" />
                    I2V Frame
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      className="hidden"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        await api.uploadSceneFrame(sc.id, "first", f);
                        setNotice("First-frame image attached for Image-to-Video.");
                      }}
                    />
                  </label>

                  <button
                    onClick={() => handleVariations(sc.id)}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 font-medium text-slate-700 hover:bg-slate-50"
                    title="Create Variations"
                  >
                    <GitBranch className="h-3 w-3" />
                    Vars
                  </button>

                  {sc.video_clip_path && (
                    <button
                      onClick={() => handleExtendScene(sc.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 font-medium text-slate-700 hover:bg-slate-50"
                      title="Extend Clip"
                    >
                      +Extend
                    </button>
                  )}

                  {sc.history_json && sc.history_json.length > 0 && (
                    <span className="inline-flex items-center gap-1 text-[11px] text-slate-500">
                      <History className="h-3 w-3" />
                      {sc.history_json.length} prev
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function FlowStudioPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-slate-500">Loading Flow Studio...</div>}>
      <FlowStudioInner />
    </Suspense>
  );
}

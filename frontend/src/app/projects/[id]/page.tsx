"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  CheckCircle2,
  Download,
  FileText,
  Film,
  Image as ImageIcon,
  Layers,
  Loader2,
  Mic,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Upload,
  UserCheck,
  XCircle,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  AudioTrack,
  AvatarJob,
  CharacterRecord,
  Project,
  ScriptRecord,
  VideoExport,
  VisualScene,
  VoicePreset,
} from "@/lib/types";

type StudioTab = "script" | "avatar" | "visuals" | "export";

function ProjectStudioInner() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [tab, setTab] = useState<StudioTab>("script");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [project, setProject] = useState<Project | null>(null);
  const [scripts, setScripts] = useState<ScriptRecord[]>([]);
  const [voices, setVoices] = useState<VoicePreset[]>([]);
  const [audioTracks, setAudioTracks] = useState<AudioTrack[]>([]);
  const [characters, setCharacters] = useState<CharacterRecord[]>([]);
  const [avatarJobs, setAvatarJobs] = useState<AvatarJob[]>([]);
  const [scenes, setScenes] = useState<VisualScene[]>([]);
  const [exportsList, setExportsList] = useState<VideoExport[]>([]);

  // Form states
  const [scriptText, setScriptText] = useState("");
  const [voiceId, setVoiceId] = useState("af_heart");
  const [speed, setSpeed] = useState(1.0);
  const [volume, setVolume] = useState(1.0);

  const [charName, setCharName] = useState("Presenter");
  const [charFile, setCharFile] = useState<File | null>(null);
  const [avatarAdapter, setAvatarAdapter] = useState("auto");
  const [avatarFps, setAvatarFps] = useState(25);

  const [useComfyui, setUseComfyui] = useState(false);
  const [editingSceneId, setEditingSceneId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editSentence, setEditSentence] = useState("");
  const [sceneBust, setSceneBust] = useState<Record<string, string>>({});

  const [includeSubtitles, setIncludeSubtitles] = useState(true);
  const [preferNvenc, setPreferNvenc] = useState(false);
  const [exportFps, setExportFps] = useState(30);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [p, sc, v, au, ch, av, vis, ex] = await Promise.all([
        api.getProject(projectId),
        api.listScripts(projectId),
        api.listVoices(),
        api.listAudio(projectId),
        api.listCharacters(projectId),
        api.listAvatarJobs(projectId),
        api.listVisualScenes(projectId),
        api.listExports(projectId),
      ]);
      setProject(p);
      setScripts(sc);
      if (sc[0] && !scriptText) setScriptText(sc[0].raw_text);
      setVoices(v);
      setAudioTracks(au);
      setCharacters(ch);
      setAvatarJobs(av);
      setScenes(vis);
      setExportsList(ex);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load studio");
    } finally {
      setLoading(false);
    }
  }, [projectId, scriptText]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const latestAudio = audioTracks[0];
  const latestChar = characters[0];
  const latestAvatar = avatarJobs[0];
  const latestExport = exportsList[0];

  // Poll active background jobs automatically
  const hasRunningJob =
    (latestAudio && ["queued", "generating", "aligning"].includes(latestAudio.status)) ||
    (latestAvatar && ["queued", "running"].includes(latestAvatar.status)) ||
    (latestExport && ["queued", "running"].includes(latestExport.status));

  useEffect(() => {
    if (!hasRunningJob) return;
    const timer = setInterval(() => {
      loadAll();
    }, 2000);
    return () => clearInterval(timer);
  }, [hasRunningJob, loadAll]);

  const wordCount = useMemo(
    () => (scriptText.trim() ? scriptText.trim().split(/\s+/).length : 0),
    [scriptText],
  );
  const estSeconds = Math.round((wordCount / 150) * 60);

  const runAction = async (label: string, fn: () => Promise<void>) => {
    setBusyAction(label);
    setError(null);
    setNotice(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed`);
    } finally {
      setBusyAction(null);
    }
  };

  // --- Handlers ---
  const handleSaveScriptAndGenerateAudio = () =>
    runAction("audio", async () => {
      const saved = await api.createScript(projectId, scriptText);
      await api.generateAudio(projectId, {
        script_id: saved.id,
        script_text: scriptText,
        voice_id: voiceId,
        speed,
        volume,
        auto_align: true,
      });
      setNotice("Script saved and narration generation started.");
      await loadAll();
    });

  const handleUploadCharacter = (e: React.FormEvent) => {
    e.preventDefault();
    if (!charFile) return;
    runAction("character", async () => {
      const ch = await api.uploadCharacter(projectId, charName, charFile);
      await api.approveCharacter(ch.id);
      setCharFile(null);
      setNotice("Character uploaded, normalized to 1080×960, and approved.");
      await loadAll();
    });
  };

  const handleGenerateAvatar = () =>
    runAction("avatar", async () => {
      if (!latestChar || !latestAudio) {
        throw new Error("Upload a character and complete narration audio first.");
      }
      await api.generateAvatar(projectId, {
        character_id: latestChar.id,
        audio_id: latestAudio.id,
        adapter: avatarAdapter,
        fps: avatarFps,
      });
      setNotice("Avatar animation job started.");
      await loadAll();
    });

  const handleGenerateVisuals = () =>
    runAction("visuals", async () => {
      if (!latestAudio) throw new Error("Complete narration audio first.");
      await api.generateVisuals(projectId, {
        audio_id: latestAudio.id,
        use_comfyui: useComfyui,
        render_video: false,
        fps: 25,
      });
      setNotice("Educational visual scenes generated from aligned narration.");
      await loadAll();
    });

  const handleSaveSceneEdit = (sceneId: string) =>
    runAction("scene-edit", async () => {
      await api.updateVisualScene(sceneId, {
        title_text: editTitle,
        sentence_text: editSentence,
        body_bullets: [editSentence],
      });
      setEditingSceneId(null);
      setSceneBust((prev) => ({ ...prev, [sceneId]: String(Date.now()) }));
      await loadAll();
    });

  const handleMoveScene = (index: number, dir: -1 | 1) =>
    runAction("reorder", async () => {
      const target = index + dir;
      if (target < 0 || target >= scenes.length) return;
      const copy = [...scenes];
      const [moved] = copy.splice(index, 1);
      copy.splice(target, 0, moved);
      await api.reorderVisualScenes(
        projectId,
        copy.map((s) => s.id),
      );
      await loadAll();
    });

  const handleStartExport = () =>
    runAction("export", async () => {
      if (!latestAudio || !latestAvatar) {
        throw new Error("Both completed audio and avatar video are required.");
      }
      await api.createExport(projectId, {
        audio_id: latestAudio.id,
        avatar_job_id: latestAvatar.id,
        include_subtitles: includeSubtitles,
        prefer_nvenc: preferNvenc,
        fps: exportFps,
      });
      setNotice("Final 1080×1920 MP4 composition started.");
      await loadAll();
    });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-blue-600" />
        Loading studio workspace...
      </div>
    );
  }

  if (!project) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        {error || "Project not found."}
      </div>
    );
  }

  const stageItems = [
    {
      label: "1. Script",
      status: scripts.length > 0 ? "completed" : "pending",
      pct: scripts.length > 0 ? 100 : 0,
    },
    {
      label: "2. Audio & Alignment",
      status: latestAudio?.status || "pending",
      pct: latestAudio?.progress_pct || 0,
    },
    {
      label: "3. Visuals",
      status: scenes.length > 0 ? "completed" : "pending",
      pct: scenes.length > 0 ? 100 : 0,
    },
    {
      label: "4. Avatar",
      status: latestAvatar?.status || "pending",
      pct: latestAvatar?.progress_pct || 0,
    },
    {
      label: "5. Composition",
      status: latestExport?.status || "pending",
      pct: latestExport?.progress_pct || 0,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="rounded-xl border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-100"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-slate-900">{project.title}</h1>
            <p className="text-xs text-slate-500">
              {project.resolution} • Top/Bottom 50/50 • Target {project.target_duration_sec}s
            </p>
          </div>
        </div>

        {/* Stage Tabs */}
        <div className="flex flex-wrap gap-1.5 rounded-xl border border-slate-200 bg-white p-1">
          {[
            { id: "script", label: "1. Script & Voice", icon: Mic },
            { id: "avatar", label: "2. Character & Avatar", icon: UserCheck },
            { id: "visuals", label: "3. Visuals", icon: Layers },
            { id: "export", label: "4. Progress & Export", icon: Film },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id as StudioTab)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                tab === id
                  ? "bg-blue-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Live Pipeline Progress Strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {stageItems.map((st) => (
          <div key={st.label} className="rounded-xl border border-slate-200 bg-white p-3">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
              <span>{st.label}</span>
              <span className="text-[11px] uppercase text-slate-500">{st.status}</span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full transition-all ${
                  st.status === "failed"
                    ? "bg-red-500"
                    : st.status === "completed"
                      ? "bg-emerald-500"
                      : "bg-blue-600"
                }`}
                style={{ width: `${st.pct}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3.5 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 text-sm text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {/* TAB 1: SCRIPT & VOICE */}
      {tab === "script" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 lg:col-span-2">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-bold text-slate-900">
                <FileText className="h-4 w-4 text-blue-600" />
                Educational Script
              </h2>
              <span className="text-xs font-medium text-slate-500">
                {wordCount} words • ~{estSeconds}s estimated
              </span>
            </div>
            <textarea
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
              rows={12}
              placeholder="Write or paste your educational narration script (~300 words for 2 minutes)..."
              className="mt-3 w-full rounded-xl border border-slate-300 p-3.5 text-sm leading-relaxed focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-bold text-slate-900">AI Narration (Kokoro-82M)</h2>
            <div>
              <label className="block text-xs font-semibold text-slate-700">Voice Preset</label>
              <select
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {voices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.accent})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="flex justify-between text-xs font-semibold text-slate-700">
                <span>Speaking Speed</span>
                <span>{speed.toFixed(2)}x</span>
              </label>
              <input
                type="range"
                min={0.7}
                max={1.5}
                step={0.05}
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                className="mt-1 w-full"
              />
            </div>
            <div>
              <label className="flex justify-between text-xs font-semibold text-slate-700">
                <span>Volume</span>
                <span>{Math.round(volume * 100)}%</span>
              </label>
              <input
                type="range"
                min={0.5}
                max={1.5}
                step={0.05}
                value={volume}
                onChange={(e) => setVolume(Number(e.target.value))}
                className="mt-1 w-full"
              />
            </div>

            <button
              onClick={handleSaveScriptAndGenerateAudio}
              disabled={busyAction === "audio" || scriptText.trim().length < 10}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {busyAction === "audio" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Mic className="h-4 w-4" />
              )}
              Save Script & Generate Audio
            </button>

            {latestAudio && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs">
                <div className="flex items-center justify-between font-semibold text-slate-800">
                  <span>Latest Audio ({latestAudio.voice_id})</span>
                  <span>{latestAudio.status}</span>
                </div>
                {latestAudio.error_message && (
                  <p className="mt-1 text-red-600">{latestAudio.error_message}</p>
                )}
                {latestAudio.status === "completed" && (
                  <>
                    <p className="mt-1 text-slate-600">
                      Duration: {latestAudio.duration_sec.toFixed(2)}s •{" "}
                      {latestAudio.alignment_json?.words?.length || 0} aligned words
                    </p>
                    <audio
                      controls
                      src={api.audioPreviewUrl(latestAudio.id)}
                      className="mt-2 w-full"
                    />
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: CHARACTER & AVATAR */}
      {tab === "avatar" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <form
            onSubmit={handleUploadCharacter}
            className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5"
          >
            <h2 className="text-base font-bold text-slate-900">1. Character Reference</h2>
            <div>
              <label className="block text-xs font-semibold text-slate-700">Character Name</label>
              <input
                value={charName}
                onChange={(e) => setCharName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700">
                Reference Portrait (PNG/JPG/WEBP)
              </label>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(e) => setCharFile(e.target.files?.[0] || null)}
                className="mt-1 w-full text-xs text-slate-600"
                required
              />
            </div>
            <button
              type="submit"
              disabled={!charFile || busyAction === "character"}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50"
            >
              <Upload className="h-4 w-4" />
              Upload & Approve Character
            </button>

            {latestChar && (
              <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span>{latestChar.name} (1080×960 Canonical)</span>
                  <span className="text-emerald-700">
                    {latestChar.identity_pack_json?.approved ? "Approved" : "Ready"}
                  </span>
                </div>
                <img
                  src={api.characterPreviewUrl(latestChar.id)}
                  alt={latestChar.name}
                  className="mt-2 max-h-64 w-full rounded-lg object-contain bg-slate-900"
                />
              </div>
            )}
          </form>

          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-bold text-slate-900">2. Avatar Animation Engine</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Adapter</label>
                <select
                  value={avatarAdapter}
                  onChange={(e) => setAvatarAdapter(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="auto">Auto (Best Available)</option>
                  <option value="local_expressive">Local Expressive (6GB Safe)</option>
                  <option value="comfyui_echomimic_v2">ComfyUI EchoMimicV2</option>
                  <option value="cloud_avatar">Cloud GPU Avatar</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">FPS</label>
                <select
                  value={avatarFps}
                  onChange={(e) => setAvatarFps(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value={25}>25 FPS</option>
                  <option value={30}>30 FPS</option>
                </select>
              </div>
            </div>

            <button
              onClick={handleGenerateAvatar}
              disabled={!latestChar || latestAudio?.status !== "completed" || busyAction === "avatar"}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {busyAction === "avatar" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Generate Synchronized Avatar
            </button>

            {latestAvatar && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs">
                <div className="flex items-center justify-between font-semibold">
                  <span>Adapter: {latestAvatar.adapter_used}</span>
                  <span>
                    {latestAvatar.status} ({latestAvatar.progress_pct}%)
                  </span>
                </div>
                {latestAvatar.error_message && (
                  <p className="mt-1 text-red-600">{latestAvatar.error_message}</p>
                )}
                {latestAvatar.continuity_report_json && (
                  <p className="mt-1 text-slate-600">
                    Drift: {latestAvatar.continuity_report_json.av_drift_ms}ms • SSIM min:{" "}
                    {latestAvatar.continuity_report_json.boundary_ssim_min}
                  </p>
                )}
                {latestAvatar.status === "completed" && (
                  <video
                    controls
                    src={api.avatarPreviewUrl(latestAvatar.id)}
                    className="mt-2 max-h-64 w-full rounded-lg bg-black"
                  />
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: EDUCATIONAL VISUALS */}
      {tab === "visuals" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-4">
              <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={useComfyui}
                  onChange={(e) => setUseComfyui(e.target.checked)}
                />
                Use ComfyUI AI Illustrations (if online)
              </label>
            </div>
            <button
              onClick={handleGenerateVisuals}
              disabled={latestAudio?.status !== "completed" || busyAction === "visuals"}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {busyAction === "visuals" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Generate Visual Scenes from Audio
            </button>
          </div>

          {scenes.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
              No visual scenes generated yet. Complete audio alignment first, then click Generate Visual Scenes.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {scenes.map((scene, idx) => (
                <div
                  key={scene.id}
                  className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span className="font-bold text-slate-900">
                      Scene #{idx + 1} • {scene.visual_format}
                    </span>
                    <span>
                      {(scene.start_ms / 1000).toFixed(1)}s – {(scene.end_ms / 1000).toFixed(1)}s
                    </span>
                  </div>

                  <img
                    src={api.visualPreviewUrl(scene.id, "image", sceneBust[scene.id])}
                    alt={scene.title_text}
                    className="mt-2 aspect-[9/8] w-full rounded-xl border border-slate-200 object-cover"
                  />

                  {editingSceneId === scene.id ? (
                    <div className="mt-3 space-y-2">
                      <input
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-semibold"
                      />
                      <textarea
                        value={editSentence}
                        onChange={(e) => setEditSentence(e.target.value)}
                        rows={2}
                        className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveSceneEdit(scene.id)}
                          className="rounded-lg bg-blue-600 px-3 py-1 text-xs font-semibold text-white"
                        >
                          Save & Re-render
                        </button>
                        <button
                          onClick={() => setEditingSceneId(null)}
                          className="rounded-lg px-3 py-1 text-xs text-slate-600 hover:bg-slate-100"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3">
                      <div className="text-sm font-bold text-slate-900">{scene.title_text}</div>
                      <p className="mt-0.5 text-xs text-slate-600 line-clamp-2">
                        {scene.sentence_text}
                      </p>
                    </div>
                  )}

                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2.5 text-xs">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleMoveScene(idx, -1)}
                        disabled={idx === 0}
                        className="rounded p-1 hover:bg-slate-100 disabled:opacity-30"
                        title="Move Up"
                      >
                        <ArrowUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handleMoveScene(idx, 1)}
                        disabled={idx === scenes.length - 1}
                        className="rounded p-1 hover:bg-slate-100 disabled:opacity-30"
                        title="Move Down"
                      >
                        <ArrowDown className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => {
                          setEditingSceneId(scene.id);
                          setEditTitle(scene.title_text);
                          setEditSentence(scene.sentence_text);
                        }}
                        className="rounded px-2 py-1 font-medium text-slate-700 hover:bg-slate-100"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() =>
                          runAction("regen", async () => {
                            await api.regenerateVisualScene(scene.id, useComfyui);
                            setSceneBust((prev) => ({ ...prev, [scene.id]: String(Date.now()) }));
                            await loadAll();
                          })
                        }
                        className="inline-flex items-center gap-1 rounded px-2 py-1 font-medium text-slate-700 hover:bg-slate-100"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Regen
                      </button>
                      <label className="inline-flex cursor-pointer items-center gap-1 rounded px-2 py-1 font-medium text-slate-700 hover:bg-slate-100">
                        <ImageIcon className="h-3 w-3" />
                        Image
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          className="hidden"
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (!f) return;
                            runAction("replace", async () => {
                              await api.replaceSceneImage(scene.id, f);
                              setSceneBust((prev) => ({ ...prev, [scene.id]: String(Date.now()) }));
                              await loadAll();
                            });
                          }}
                        />
                      </label>
                    </div>

                    <button
                      onClick={() =>
                        runAction("approve", async () => {
                          await api.approveVisualScene(scene.id);
                          await loadAll();
                        })
                      }
                      className={`rounded-full px-2.5 py-0.5 font-semibold ${
                        scene.approved
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-slate-100 text-slate-700 hover:bg-emerald-50"
                      }`}
                    >
                      {scene.approved ? "Approved" : "Approve"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: PROGRESS, PREVIEW & EXPORT */}
      {tab === "export" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-bold text-slate-900">Export Settings (1080×1920)</h2>
            <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
              <input
                type="checkbox"
                checked={includeSubtitles}
                onChange={(e) => setIncludeSubtitles(e.target.checked)}
              />
              Burn Synchronized Captions (.ASS)
            </label>
            <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
              <input
                type="checkbox"
                checked={preferNvenc}
                onChange={(e) => setPreferNvenc(e.target.checked)}
              />
              Prefer NVENC Hardware Encode (auto-fallback CPU)
            </label>
            <div>
              <label className="block text-xs font-semibold text-slate-700">Frame Rate</label>
              <select
                value={exportFps}
                onChange={(e) => setExportFps(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value={30}>30 FPS (Standard)</option>
                <option value={24}>24 FPS</option>
              </select>
            </div>

            <button
              onClick={handleStartExport}
              disabled={
                latestAudio?.status !== "completed" ||
                latestAvatar?.status !== "completed" ||
                scenes.length === 0 ||
                busyAction === "export"
              }
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {busyAction === "export" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Film className="h-4 w-4" />
              )}
              Export Final 1080×1920 MP4
            </button>

            {latestExport && ["queued", "running"].includes(latestExport.status) && (
              <button
                onClick={() =>
                  runAction("cancel", async () => {
                    await api.cancelExport(latestExport.id);
                    await loadAll();
                  })
                }
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-xs font-semibold text-red-700 hover:bg-red-100"
              >
                <XCircle className="h-4 w-4" />
                Cancel Active Export
              </button>
            )}

            {/* Export History */}
            <div className="border-t border-slate-100 pt-4">
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">
                Export History
              </h3>
              <div className="mt-2 space-y-2">
                {exportsList.map((ex) => (
                  <div
                    key={ex.id}
                    className="flex items-center justify-between rounded-xl border border-slate-200 p-2.5 text-xs"
                  >
                    <div>
                      <div className="font-semibold text-slate-800">
                        {ex.status} ({ex.progress_pct}%) • {ex.encoder_used}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {ex.duration_sec.toFixed(2)}s • {ex.width}×{ex.height}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() =>
                          runAction("reexport", async () => {
                            await api.reExport(ex.id);
                            await loadAll();
                          })
                        }
                        className="rounded p-1.5 text-slate-600 hover:bg-slate-100"
                        title="Re-export"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </button>
                      {ex.status === "completed" && (
                        <a
                          href={api.exportDownloadUrl(ex.id)}
                          className="rounded p-1.5 text-blue-600 hover:bg-blue-50"
                          title="Download MP4"
                        >
                          <Download className="h-3.5 w-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 lg:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-bold text-slate-900">Final Vertical Video Preview</h2>
              {latestExport?.status === "completed" && (
                <a
                  href={api.exportDownloadUrl(latestExport.id)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
                >
                  <Download className="h-3.5 w-3.5" />
                  Download Final MP4
                </a>
              )}
            </div>

            {latestExport?.status === "completed" ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <video
                  controls
                  src={api.exportPreviewUrl(latestExport.id)}
                  className="mx-auto aspect-[9/16] max-h-[540px] rounded-2xl border border-slate-200 bg-black shadow-md"
                />
                <div className="space-y-3 text-xs">
                  <h3 className="font-bold text-slate-900">Validation Report</h3>
                  {latestExport.validation_report_json && (
                    <div className="space-y-1.5 rounded-xl bg-slate-50 p-3 text-slate-700">
                      <div>
                        Resolution: {latestExport.validation_report_json.width}×
                        {latestExport.validation_report_json.height} (
                        {latestExport.validation_report_json.aspect_ratio})
                      </div>
                      <div>
                        FPS: {latestExport.validation_report_json.fps} • Codecs:{" "}
                        {latestExport.validation_report_json.video_codec} /{" "}
                        {latestExport.validation_report_json.audio_codec}
                      </div>
                      <div>
                        A/V Drift: {latestExport.validation_report_json.av_drift_ms} ms • Black
                        Frames: {latestExport.validation_report_json.black_frame_count}
                      </div>
                    </div>
                  )}
                  <h3 className="font-bold text-slate-900">Composition Logs</h3>
                  <div className="max-h-56 space-y-1 overflow-y-auto rounded-xl bg-slate-900 p-3 font-mono text-[11px] text-slate-200">
                    {(latestExport.logs_json || []).map((l, idx) => (
                      <div key={idx}>
                        [{l.stage}] {l.message}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center text-sm text-slate-500">
                {latestExport
                  ? `Export status: ${latestExport.status} (${latestExport.progress_pct}%)${
                      latestExport.error_message ? ` — ${latestExport.error_message}` : ""
                    }`
                  : "Complete Audio, Character/Avatar, and Visuals, then click Export Final 1080×1920 MP4."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ProjectStudioPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24 text-slate-500">
          Loading studio workspace...
        </div>
      }
    >
      <ProjectStudioInner />
    </Suspense>
  );
}

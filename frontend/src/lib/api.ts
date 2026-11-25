import type {
  AudioTrack,
  AvatarJob,
  CharacterRecord,
  HealthDetailed,
  Project,
  ScriptRecord,
  VideoExport,
  VisualScene,
  VoicePreset,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("studio_access_token");
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("studio_access_token", token);
  else localStorage.removeItem("studio_access_token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  healthDetailed: () => request<HealthDetailed>("/health/detailed"),
  authMe: () => request<{ authenticated: boolean; username: string; auth_required: boolean }>("/api/v1/auth/me"),
  login: (username: string, password: string) =>
    request<{ access_token: string; username: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  // Projects
  listProjects: () => request<Project[]>("/api/v1/projects"),
  getProject: (id: string) => request<Project>(`/api/v1/projects/${id}`),
  createProject: (payload: {
    title: string;
    description?: string;
    target_duration_sec: number;
    compute_mode: string;
  }) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProject: (id: string, payload: Partial<Project>) =>
    request<Project>(`/api/v1/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  duplicateProject: (id: string) =>
    request<Project>(`/api/v1/projects/${id}/duplicate`, { method: "POST" }),
  deleteProject: (id: string) =>
    request<void>(`/api/v1/projects/${id}`, { method: "DELETE" }),

  // Scripts
  listScripts: (projectId: string) =>
    request<ScriptRecord[]>(`/api/v1/projects/${projectId}/scripts`),
  createScript: (projectId: string, raw_text: string) =>
    request<ScriptRecord>(`/api/v1/projects/${projectId}/scripts`, {
      method: "POST",
      body: JSON.stringify({ raw_text }),
    }),

  // Characters
  listCharacters: (projectId: string) =>
    request<CharacterRecord[]>(`/api/v1/projects/${projectId}/characters`),
  uploadCharacter: (projectId: string, name: string, file: File) => {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("image", file);
    return request<CharacterRecord>(`/api/v1/projects/${projectId}/characters`, {
      method: "POST",
      body: fd,
    });
  },
  approveCharacter: (characterId: string) =>
    request<CharacterRecord>(`/api/v1/characters/${characterId}/approve`, {
      method: "POST",
    }),
  characterPreviewUrl: (characterId: string) =>
    `${API_BASE}/api/v1/characters/${characterId}/preview`,

  // Audio
  listVoices: () => request<VoicePreset[]>("/api/v1/audio/voices"),
  listAudio: (projectId: string) =>
    request<AudioTrack[]>(`/api/v1/projects/${projectId}/audio`),
  generateAudio: (
    projectId: string,
    payload: {
      script_id?: string;
      script_text?: string;
      voice_id: string;
      speed: number;
      volume: number;
      auto_align: boolean;
    },
  ) =>
    request<AudioTrack>(`/api/v1/projects/${projectId}/audio/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAudio: (audioId: string) => request<AudioTrack>(`/api/v1/audio/${audioId}`),
  audioPreviewUrl: (audioId: string) => `${API_BASE}/api/v1/audio/${audioId}/preview`,

  // Avatar
  listAvatarJobs: (projectId: string) =>
    request<AvatarJob[]>(`/api/v1/projects/${projectId}/avatar`),
  generateAvatar: (
    projectId: string,
    payload: { character_id: string; audio_id: string; adapter: string; fps: number },
  ) =>
    request<AvatarJob>(`/api/v1/projects/${projectId}/avatar/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAvatarJob: (avatarJobId: string) =>
    request<AvatarJob>(`/api/v1/avatar/${avatarJobId}`),
  avatarPreviewUrl: (avatarJobId: string) =>
    `${API_BASE}/api/v1/avatar/${avatarJobId}/preview`,

  // Visuals
  listVisualScenes: (projectId: string) =>
    request<VisualScene[]>(`/api/v1/projects/${projectId}/visuals/scenes`),
  generateVisuals: (
    projectId: string,
    payload: { audio_id: string; use_comfyui: boolean; render_video: boolean; fps: number },
  ) =>
    request<VisualScene[]>(`/api/v1/projects/${projectId}/visuals/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateVisualScene: (sceneId: string, payload: Record<string, unknown>) =>
    request<VisualScene>(`/api/v1/visuals/scenes/${sceneId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  regenerateVisualScene: (sceneId: string, useComfyui = false) =>
    request<VisualScene>(
      `/api/v1/visuals/scenes/${sceneId}/regenerate?use_comfyui=${useComfyui}`,
      { method: "POST" },
    ),
  replaceSceneImage: (sceneId: string, file: File) => {
    const fd = new FormData();
    fd.append("image", file);
    return request<VisualScene>(`/api/v1/visuals/scenes/${sceneId}/replace-image`, {
      method: "POST",
      body: fd,
    });
  },
  reorderVisualScenes: (projectId: string, scene_ids: string[]) =>
    request<VisualScene[]>(`/api/v1/projects/${projectId}/visuals/scenes/reorder`, {
      method: "POST",
      body: JSON.stringify({ scene_ids }),
    }),
  approveVisualScene: (sceneId: string) =>
    request<VisualScene>(`/api/v1/visuals/scenes/${sceneId}/approve`, {
      method: "POST",
    }),
  visualPreviewUrl: (sceneId: string, kind: "image" | "video" = "image", cacheBust?: string) =>
    `${API_BASE}/api/v1/visuals/scenes/${sceneId}/preview?kind=${kind}${cacheBust ? `&v=${cacheBust}` : ""}`,

  // Exports
  listExports: (projectId: string) =>
    request<VideoExport[]>(`/api/v1/projects/${projectId}/exports`),
  createExport: (
    projectId: string,
    payload: {
      audio_id: string;
      avatar_job_id: string;
      include_subtitles: boolean;
      prefer_nvenc: boolean;
      fps: number;
    },
  ) =>
    request<VideoExport>(`/api/v1/projects/${projectId}/exports`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getExport: (exportId: string) => request<VideoExport>(`/api/v1/exports/${exportId}`),
  cancelExport: (exportId: string) =>
    request<VideoExport>(`/api/v1/exports/${exportId}/cancel`, { method: "POST" }),
  reExport: (exportId: string) =>
    request<VideoExport>(`/api/v1/exports/${exportId}/re-export`, { method: "POST" }),
  exportPreviewUrl: (exportId: string) => `${API_BASE}/api/v1/exports/${exportId}/preview`,
  exportDownloadUrl: (exportId: string) => `${API_BASE}/api/v1/exports/${exportId}/download`,
};

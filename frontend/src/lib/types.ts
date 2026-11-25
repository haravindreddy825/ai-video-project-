export interface Project {
  id: string;
  title: string;
  description: string | null;
  target_duration_sec: number;
  resolution: string;
  layout_mode: string;
  compute_mode: "local_hybrid" | "local_only" | "cloud_preferred";
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ScriptRecord {
  id: string;
  project_id: string;
  version: number;
  raw_text: string;
  beats_json: unknown;
  estimated_duration_sec: number;
  created_at: string;
}

export interface CharacterRecord {
  id: string;
  project_id: string;
  name: string;
  reference_image_path: string;
  width: number;
  height: number;
  identity_pack_json: {
    canonical_image_path?: string;
    width?: number;
    height?: number;
    approved?: boolean;
    locked?: boolean;
  } | null;
  created_at: string;
}

export interface VoicePreset {
  id: string;
  name: string;
  gender: "female" | "male";
  accent: string;
  language: string;
  description: string;
}

export interface AudioTrack {
  id: string;
  project_id: string;
  script_id: string | null;
  engine: string;
  voice_id: string;
  speed: number;
  volume: number;
  status: string;
  progress_pct: number;
  audio_file_path: string | null;
  sample_rate: number;
  duration_sec: number;
  original_script_text: string;
  alignment_json: {
    full_transcript?: string;
    sentences?: Array<{ index: number; text: string; start_ms: number; end_ms: number }>;
    words?: Array<{ word: string; start_ms: number; end_ms: number }>;
    pauses?: Array<{ after_sentence_index: number; duration_ms: number }>;
    validation?: { passed: boolean; coverage_ratio: number; warnings: string[] };
  } | null;
  script_intelligence_json: {
    total_sentences?: number;
    sentences?: Array<{
      index: number;
      sentence_type: string;
      emotion: string;
      facial_expression: string;
      hand_gesture: string;
      highlight_words: string[];
    }>;
  } | null;
  error_message: string | null;
}

export interface AvatarJob {
  id: string;
  project_id: string;
  character_id: string;
  audio_id: string;
  adapter_used: string;
  status: string;
  progress_pct: number;
  width: number;
  height: number;
  fps: number;
  duration_sec: number;
  video_file_path: string | null;
  continuity_report_json: {
    segments_checked: number;
    boundary_ssim_min: number;
    av_drift_ms: number;
    passed: boolean;
    warnings: string[];
  } | null;
  error_message: string | null;
}

export interface VisualScene {
  id: string;
  project_id: string;
  audio_id: string;
  order_index: number;
  start_ms: number;
  end_ms: number;
  sentence_text: string;
  main_concept: string;
  keywords_json: string[] | null;
  visual_format: string;
  visual_description: string;
  title_text: string;
  body_bullets_json: string[] | null;
  animation_style: string;
  transition_style: string;
  generator_used: string;
  image_path: string | null;
  video_path: string | null;
  approved: boolean;
}

export interface VideoExport {
  id: string;
  project_id: string;
  audio_id: string;
  avatar_job_id: string;
  status: string;
  progress_pct: number;
  encoder_used: string;
  include_subtitles: boolean;
  width: number;
  height: number;
  fps: number;
  duration_sec: number;
  output_mp4_path: string | null;
  validation_report_json: {
    width: number;
    height: number;
    aspect_ratio: string;
    fps: number;
    video_codec: string;
    audio_codec: string;
    pixel_format: string;
    duration_sec: number;
    av_drift_ms: number;
    black_frame_count: number;
    passed: boolean;
    warnings: string[];
  } | null;
  logs_json: Array<{ timestamp: string; stage: string; message: string }> | null;
  error_message: string | null;
}

export interface HealthDetailed {
  status: string;
  database: string;
  redis: string;
  gpu: { available: boolean; name: string; total_mb: number; free_mb: number };
  storage: { free_gb: number; total_gb: number };
  ram?: { total_gb: number; available_gb: number; percent: number };
}

"use client";

import { useEffect, useState } from "react";
import { Mic } from "lucide-react";
import { api } from "@/lib/api";
import type { VoicePreset } from "@/lib/types";

export default function VoicesPage() {
  const [voices, setVoices] = useState<VoicePreset[]>([]);

  useEffect(() => {
    api.listVoices().then(setVoices).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <Mic className="h-6 w-6 text-blue-600" />
          My Voices (Kokoro-82M)
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Saved open-source narration voice profiles available for both Flow cinematic videos and 9:16 educational videos.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {voices.map((v) => (
          <div key={v.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-900">{v.name}</h3>
              <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
                {v.gender}
              </span>
            </div>
            <p className="mt-1 text-xs font-medium text-slate-500">
              {v.accent} • ID: {v.id}
            </p>
            <p className="mt-2 text-xs text-slate-600">{v.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

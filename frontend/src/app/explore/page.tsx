"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Compass, Sparkles, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { FlowProviderCapability } from "@/lib/types";

const TEMPLATES = [
  {
    title: "Deep Space Discovery (2-Min Sci-Fi)",
    prompt:
      "A lone astronaut discovers an ancient glowing library buried beneath the ice of Europa. As she brushes frost from crystal shelves, holographic star maps awaken and guide her toward a hidden portal.",
  },
  {
    title: "Neural Networks Explained Visually",
    prompt:
      "Inside a luminous digital city, tiny glowing signals travel across golden bridges between neural towers. Each tower adjusts its brightness as patterns emerge from chaos into clear understanding.",
  },
  {
    title: "Ocean Conservation Documentary",
    prompt:
      "Sunlight pierces turquoise coral reefs teeming with bioluminescent sea turtles and schools of silver fish. Time-lapse currents reveal how protected marine sanctuaries restore vibrant ecosystems.",
  },
];

export default function ExplorePage() {
  const [providers, setProviders] = useState<FlowProviderCapability[]>([]);

  useEffect(() => {
    api.listFlowProviders().then(setProviders).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <Compass className="h-6 w-6 text-blue-600" />
          Explore Prompts &amp; Video Models
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Start from a curated 2-minute story template or inspect live video-generation provider capabilities and costs.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {TEMPLATES.map((t) => (
          <div key={t.title} className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div>
              <h2 className="flex items-center gap-1.5 text-sm font-bold text-slate-900">
                <Sparkles className="h-4 w-4 text-blue-600" />
                {t.title}
              </h2>
              <p className="mt-2 text-xs leading-relaxed text-slate-600">{t.prompt}</p>
            </div>
            <Link
              href={`/flow?prompt=${encodeURIComponent(t.prompt)}`}
              className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-700"
            >
              Use in Create Video
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-bold text-slate-900">Supported Video Generation Providers</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          {providers.map((p) => (
            <div key={p.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-slate-900">{p.name}</span>
                <span
                  className={`rounded-full px-2.5 py-0.5 font-semibold ${
                    p.available ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {p.available ? "Available" : "Not Configured"}
                </span>
              </div>
              <p className="mt-2 text-slate-600">{p.reason}</p>
              <div className="mt-2 space-y-1 text-slate-700">
                <div>Max clip: {p.max_clip_duration_sec}s • Resolutions: {p.resolutions.join(", ")}</div>
                <div>Estimated 120s cost: ${p.estimated_120s_cost_usd.toFixed(2)}</div>
                <div className="text-slate-500">{p.requirements}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

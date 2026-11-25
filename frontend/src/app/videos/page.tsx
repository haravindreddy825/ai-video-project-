"use client";

import { useEffect, useState } from "react";
import { Download, Film } from "lucide-react";
import { api } from "@/lib/api";
import type { FlowProject, VideoExport } from "@/lib/types";

export default function MyVideosPage() {
  const [flowVideos, setFlowVideos] = useState<FlowProject[]>([]);
  const [eduExports, setEduExports] = useState<Array<{ title: string; exp: VideoExport }>>([]);

  useEffect(() => {
    (async () => {
      const fl = await api.listFlowProjects().catch(() => []);
      setFlowVideos(fl.filter((f) => f.final_mp4_path));

      const projs = await api.listProjects().catch(() => []);
      const allEdu: Array<{ title: string; exp: VideoExport }> = [];
      for (const p of projs.slice(0, 15)) {
        const exps = await api.listExports(p.id).catch(() => []);
        for (const e of exps) {
          if (e.status === "completed") allEdu.push({ title: p.title, exp: e });
        }
      }
      setEduExports(allEdu);
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <Film className="h-6 w-6 text-blue-600" />
          My Videos
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          All completed Flow cinematic films and 9:16 educational MP4 exports ready for playback and download.
        </p>
      </div>

      {flowVideos.length === 0 && eduExports.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-slate-500">
          No completed video exports yet.
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {flowVideos.map((fv) => (
            <div key={fv.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <video controls src={api.flowFinalPreviewUrl(fv.id)} className="aspect-video w-full rounded-xl bg-black" />
              <div className="mt-3 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">{fv.title}</h3>
                  <p className="text-xs text-slate-500">Flow • {fv.duration_sec}s • {fv.aspect_ratio}</p>
                </div>
                <a
                  href={api.flowFinalDownloadUrl(fv.id)}
                  className="rounded-lg bg-blue-600 p-2 text-white hover:bg-blue-700"
                  title="Download MP4"
                >
                  <Download className="h-4 w-4" />
                </a>
              </div>
            </div>
          ))}

          {eduExports.map(({ title, exp }) => (
            <div key={exp.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <video controls src={api.exportPreviewUrl(exp.id)} className="mx-auto aspect-[9/16] max-h-72 rounded-xl bg-black" />
              <div className="mt-3 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">{title}</h3>
                  <p className="text-xs text-slate-500">Educational • {exp.duration_sec.toFixed(1)}s • {exp.width}×{exp.height}</p>
                </div>
                <a
                  href={api.exportDownloadUrl(exp.id)}
                  className="rounded-lg bg-blue-600 p-2 text-white hover:bg-blue-700"
                  title="Download MP4"
                >
                  <Download className="h-4 w-4" />
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

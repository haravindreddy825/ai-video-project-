"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Film, HardDrive, Cpu, Lock, Unlock, LogOut } from "lucide-react";
import { api, setToken } from "@/lib/api";
import type { HealthDetailed } from "@/lib/types";

export function AppHeader() {
  const [health, setHealth] = useState<HealthDetailed | null>(null);
  const [authInfo, setAuthInfo] = useState<{
    authenticated: boolean;
    username: string;
    auth_required: boolean;
  } | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [signedOut, setSignedOut] = useState(false);

  const loadStatus = async () => {
    try {
      const [h, a] = await Promise.all([api.healthDetailed(), api.authMe()]);
      setHealth(h);
      setAuthInfo(a);
    } catch {
      try {
        const h = await api.healthDetailed();
        setHealth(h);
      } catch {
        setHealth(null);
      }
      setAuthInfo({ authenticated: false, username: "", auth_required: true });
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    try {
      const res = await api.login(username, password);
      setToken(res.access_token);
      setSignedOut(false);
      setShowLogin(false);
      setPassword("");
      await loadStatus();
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Login failed");
    }
  };

  const handleLogout = () => {
    setToken(null);
    setSignedOut(true);
    setAuthInfo((prev) => (prev ? { ...prev, authenticated: false } : null));
  };

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5 text-slate-900">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white shadow-sm">
              <Film className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-bold leading-tight">OpenSource AI Video Studio</div>
              <div className="text-xs text-slate-500">9:16 Vertical (1080×1920) • Top/Bottom 50/50</div>
            </div>
          </Link>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {health ? (
              <>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-medium text-slate-700">
                  <Cpu className="h-3.5 w-3.5 text-blue-600" />
                  {health.gpu.available
                    ? `${health.gpu.name.replace("NVIDIA GeForce ", "")} (${health.gpu.free_mb} MB free)`
                    : "CPU Mode"}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-medium text-slate-700">
                  <HardDrive className="h-3.5 w-3.5 text-emerald-600" />
                  {health.storage.free_gb} GB free
                </span>
              </>
            ) : (
              <span className="rounded-full bg-amber-50 px-3 py-1 font-medium text-amber-700">
                Backend Offline
              </span>
            )}

            {authInfo?.authenticated && !signedOut ? (
              <button
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 font-medium text-slate-700 hover:bg-slate-50"
                title="Sign out"
              >
                <Unlock className="h-3.5 w-3.5 text-emerald-600" />
                {authInfo.username}
                <LogOut className="h-3 w-3 text-slate-400" />
              </button>
            ) : (
              <button
                onClick={() => setShowLogin(true)}
                className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1 font-medium text-white hover:bg-slate-800"
              >
                <Lock className="h-3.5 w-3.5" />
                Sign In
              </button>
            )}
          </div>
        </div>
      </header>

      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <form
            onSubmit={handleLogin}
            className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"
          >
            <h2 className="text-lg font-bold text-slate-900">Studio Sign In</h2>
            <p className="mt-1 text-xs text-slate-500">
              Authenticate with your local studio credentials.
            </p>
            {loginError && (
              <div className="mt-3 rounded-lg bg-red-50 p-2.5 text-xs text-red-700">
                {loginError}
              </div>
            )}
            <div className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Username</label>
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  required
                />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowLogin(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                Sign In
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

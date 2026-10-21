"use client";

import React, { useState, useEffect } from "react";
import {
  Film,
  Sparkles,
  Scissors,
  Download,
  Copy,
  Check,
  RotateCcw,
  Plus,
  RefreshCw,
  Video,
  Clapperboard,
  AlertCircle,
  FileText,
  UploadCloud,
  Activity,
  Volume2,
  Clock,
  Layers,
} from "lucide-react";

interface Project {
  id: number;
  name: string;
  slug: string;
  aspect_ratio: string;
  default_lut: string;
  trim_start_frames: number;
  trim_end_frames: number;
  daily_credits_used: number;
  monthly_credits_used: number;
  created_at: string;
  shots: Shot[];
  assets: any[];
}

interface Shot {
  id: number;
  project_id: number;
  shot_number: number;
  scene_title: string;
  flow_mode: string;
  flow_model: string;
  image_prompt: string;
  motion_prompt: string;
  camera_move: string;
  voiceover_line?: string;
  duration_seconds?: number;
  estimated_credits?: number;
  raw_start_frame: string | null;
  polished_start_frame: string | null;
  raw_end_frame: string | null;
  polished_end_frame: string | null;
  flow_video_raw: string | null;
  flow_video_trimmed: string | null;
  extracted_last_frame: string | null;
  status: "draft" | "sliced" | "polishing" | "ready_for_flow" | "awaiting_download" | "completed";
}

const API_BASE = "http://127.0.0.1:8000";

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [luts, setLuts] = useState<string[]>(["none"]);
  const [comfyStatus, setComfyStatus] = useState({ is_busy: false, current_task: "", available: false });
  const [wsConnected, setWsConnected] = useState(false);

  // UI Modals & Panels
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showPromptHelperModal, setShowPromptHelperModal] = useState(false);
  const [showMasterCutModal, setShowMasterCutModal] = useState(false);
  const [masterCutUrl, setMasterCutUrl] = useState<string | null>(null);
  const [isAssembling, setIsAssembling] = useState(false);

  // New Project Form
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectSlug, setNewProjectSlug] = useState("");
  const [newProjectAspect, setNewProjectAspect] = useState("9:16");

  // Gemini JSON Import Form
  const [importJsonText, setImportJsonText] = useState("");
  const [importError, setImportError] = useState("");

  // Grid Slicer State
  const [showSlicerDrawer, setShowSlicerDrawer] = useState(false);
  const [slicerFile, setSlicerFile] = useState<File | null>(null);
  const [slicerPreview, setSlicerPreview] = useState<string | null>(null);
  const [gutterPct, setGutterPct] = useState(1.2);
  const [gridRows, setGridRows] = useState(3);
  const [gridCols, setGridCols] = useState(3);
  const [isSlicing, setIsSlicing] = useState(false);

  // Card view preferences per shot: { [shotId]: 'start' | 'end' | 'polished' | 'video' }
  const [viewModes, setViewModes] = useState<Record<number, "start" | "end" | "polished" | "video">>({});
  const [copiedShotId, setCopiedShotId] = useState<number | null>(null);

  // WebSocket Connection
  useEffect(() => {
    let ws: WebSocket;
    function connect() {
      ws = new WebSocket("ws://127.0.0.1:8000/ws");
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connect, 3000);
      };
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (
            msg.type === "shot_updated" ||
            msg.type === "clip_ingested" ||
            msg.type === "grid_sliced" ||
            msg.type === "shots_updated" ||
            msg.type === "shot_polishing"
          ) {
            fetchProjects();
          }
        } catch (e) {
          console.error("WS error:", e);
        }
      };
    }
    connect();
    return () => ws && ws.close();
  }, []);

  // Poll Comfy status & load projects
  useEffect(() => {
    fetchProjects();
    fetchLuts();
    const interval = setInterval(() => {
      fetchComfyStatus();
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  async function fetchProjects() {
    try {
      const res = await fetch(`${API_BASE}/api/projects`);
      const data = await res.json();
      setProjects(data);
      if (data && data.length > 0) {
        if (!selectedProject) {
          // Default to latest or vertical genesis project if present
          const genesis = data.find((p: Project) => p.slug === "genesis_creation_vertical");
          setSelectedProject(genesis || data[0]);
        } else {
          const updated = data.find((p: Project) => p.id === selectedProject.id);
          if (updated) setSelectedProject(updated);
        }
      }
    } catch (e) {
      console.error("Failed to load projects", e);
    }
  }

  async function fetchLuts() {
    try {
      const res = await fetch(`${API_BASE}/api/luts`);
      const data = await res.json();
      setLuts(data);
    } catch (e) {
      console.error("Failed to load LUTs", e);
    }
  }

  async function fetchComfyStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/comfy/status`);
      const data = await res.json();
      setComfyStatus(data);
    } catch (e) {
      // Ignore poll fail
    }
  }

  // Create Project
  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    const slug = newProjectSlug.trim() || newProjectName.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newProjectName,
          slug,
          aspect_ratio: newProjectAspect,
          default_lut: "primeval_imax_65mm",
        }),
      });
      const created = await res.json();
      await fetchProjects();
      setSelectedProject(created);
      setShowNewProjectModal(false);
      setNewProjectName("");
      setNewProjectSlug("");
    } catch (e) {
      console.error(e);
    }
  }

  // Import JSON Shots from Gemini
  async function handleImportJson(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProject) return;
    setImportError("");
    try {
      let parsed = JSON.parse(importJsonText);
      if (!Array.isArray(parsed) && parsed.shots) {
        parsed = parsed.shots;
      }
      if (!Array.isArray(parsed)) {
        throw new Error("Input must be a JSON array of shot objects.");
      }

      const res = await fetch(`${API_BASE}/api/projects/${selectedProject.id}/import-shots`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (!res.ok) throw new Error("Failed to import shots");
      const updated = await res.json();
      setSelectedProject(updated);
      setShowImportModal(false);
      setImportJsonText("");
    } catch (err: any) {
      setImportError(err.message || "Invalid JSON format");
    }
  }

  // Slice Contact Sheet
  async function handleSliceGrid() {
    if (!selectedProject || !slicerFile) return;
    setIsSlicing(true);
    const formData = new FormData();
    formData.append("file", slicerFile);
    formData.append("rows", gridRows.toString());
    formData.append("cols", gridCols.toString());
    formData.append("gutter_pct", (gutterPct / 100).toString());

    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProject.id}/slice-grid`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedProject(updated);
        setShowSlicerDrawer(false);
        setSlicerFile(null);
        setSlicerPreview(null);
      }
    } catch (e) {
      console.error("Slice error", e);
    } finally {
      setIsSlicing(false);
    }
  }

  // Polish Shot
  async function handlePolishShot(shotId: number) {
    try {
      await fetch(`${API_BASE}/api/shots/${shotId}/polish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ denoise: 0.28 }),
      });
      fetchProjects();
    } catch (e) {
      console.error("Polish error", e);
    }
  }

  // Polish All
  async function handlePolishAll() {
    if (!selectedProject) return;
    try {
      await fetch(`${API_BASE}/api/projects/${selectedProject.id}/polish-all`, {
        method: "POST",
      });
    } catch (e) {
      console.error(e);
    }
  }

  // Copy Flow Prompt & Reveal
  async function handlePrepForFlow(shot: Shot) {
    try {
      const res = await fetch(`${API_BASE}/api/shots/${shot.id}/mark-awaiting-flow`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.motion_prompt) {
        await navigator.clipboard.writeText(data.motion_prompt);
      }
      setCopiedShotId(shot.id);
      setTimeout(() => setCopiedShotId(null), 3000);
      fetchProjects();
    } catch (e) {
      console.error(e);
    }
  }

  // Use Previous Shot's Final Frame
  async function handleUsePrevLastFrame(shotId: number) {
    try {
      const res = await fetch(`${API_BASE}/api/shots/${shotId}/use-prev-last-frame`, {
        method: "POST",
      });
      if (res.ok) fetchProjects();
    } catch (e) {
      console.error(e);
    }
  }

  // Manual Attach Clip
  async function handleManualAttachClip(shotId: number, file: File) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/shots/${shotId}/attach-clip`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) fetchProjects();
    } catch (e) {
      console.error("Manual attach error", e);
    }
  }

  // Assemble Master Cut
  async function handleAssembleMasterCut() {
    if (!selectedProject) return;
    setIsAssembling(true);
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProject.id}/assemble`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setMasterCutUrl(`${API_BASE}${data.master_url}?t=${Date.now()}`);
        setShowMasterCutModal(true);
      } else {
        const err = await res.json();
        alert(`Assembly error: ${err.detail}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsAssembling(false);
    }
  }

  // Update Project Setting
  async function handleUpdateProjectSetting(key: string, value: any) {
    if (!selectedProject) return;
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProject.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: value }),
      });
      const updated = await res.json();
      setSelectedProject(updated);
      fetchProjects();
    } catch (e) {
      console.error(e);
    }
  }

  const isVertical = selectedProject?.aspect_ratio === "9:16";
  const dailyCredits = selectedProject?.daily_credits_used || 0;
  const monthlyCredits = selectedProject?.monthly_credits_used || 0;
  const dailyRemaining = Math.max(0, 50 - dailyCredits);
  const monthlyRemaining = Math.max(0, 1000 - monthlyCredits);

  return (
    <div className="flex flex-col min-h-screen bg-zinc-950 text-zinc-100 selection:bg-amber-500/20">
      {/* ================= TOP HEADER BAR ================= */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-zinc-800 bg-zinc-900/90 px-6 py-3 backdrop-blur-md">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-amber-400 font-bold tracking-wider uppercase text-sm">
            <Clapperboard className="w-5 h-5 text-amber-500" />
            <span>Flow Companion Studio</span>
          </div>

          <div className="h-4 w-[1px] bg-zinc-700" />

          {/* Project Selector */}
          <div className="flex items-center space-x-2">
            <select
              value={selectedProject?.id || ""}
              onChange={(e) => {
                const p = projects.find((proj) => proj.id === Number(e.target.value));
                if (p) setSelectedProject(p);
              }}
              className="bg-zinc-800 text-zinc-100 text-sm font-medium rounded-lg px-3 py-1.5 border border-zinc-700 focus:outline-none focus:border-amber-500"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} [{p.aspect_ratio || "16:9"}]
                </option>
              ))}
            </select>

            <button
              onClick={() => setShowNewProjectModal(true)}
              className="p-1.5 rounded-lg bg-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-700 border border-zinc-700 transition"
              title="Create New Project"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>

          {/* Import Gemini Shots Button */}
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-700 border border-zinc-700 transition"
          >
            <FileText className="w-3.5 h-3.5 text-cyan-400" />
            <span>Import Gemini JSON</span>
          </button>

          {/* Master DP Prompt Guide */}
          <button
            onClick={() => setShowPromptHelperModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 border border-amber-500/30 transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Gemini 4 Argon Prompt</span>
          </button>
        </div>

        {/* Live Credit Meter & Comfy Hardware Pill */}
        <div className="flex items-center space-x-6">
          {/* Hardware & Service Status */}
          <div className="flex items-center space-x-2 text-xs">
            <span
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full font-mono font-medium ${
                comfyStatus.is_busy
                  ? "bg-amber-950/80 text-amber-300 border border-amber-700 animate-pulse"
                  : comfyStatus.available
                  ? "bg-emerald-950/70 text-emerald-300 border border-emerald-700/60"
                  : "bg-zinc-800 text-zinc-400 border border-zinc-700"
              }`}
            >
              <Activity className="w-3 h-3" />
              <span>
                {comfyStatus.is_busy
                  ? `ComfyUI: Sampling (${comfyStatus.current_task || "Locked"})`
                  : comfyStatus.available
                  ? "RX 9070 XT: Ready (batch_size: 1)"
                  : "ComfyUI: Offline (Preview Pass)"}
              </span>
            </span>

            <span
              className={`w-2 h-2 rounded-full ${wsConnected ? "bg-emerald-500" : "bg-rose-500"}`}
              title={wsConnected ? "Live WebSocket Connected" : "WebSocket Disconnected"}
            />
          </div>

          {/* Flow Credit Tracker */}
          <div className="flex items-center space-x-3 bg-zinc-800/80 border border-zinc-700/70 rounded-xl px-3 py-1.5 text-xs">
            <span className="text-zinc-400 font-medium">Flow Credits:</span>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-cyan-400 font-semibold">{dailyRemaining}</span>
              <span className="text-zinc-500">/ 50 Day</span>
            </div>
            <div className="h-3 w-[1px] bg-zinc-700" />
            <div className="flex items-center space-x-2">
              <span className="font-mono text-emerald-400 font-semibold">{monthlyRemaining}</span>
              <span className="text-zinc-500">/ 1,000 Mo</span>
            </div>
          </div>
        </div>
      </header>

      {/* ================= MAIN WORKSPACE ================= */}
      <main className="flex-1 flex flex-col p-6 space-y-6 max-w-[1800px] w-full mx-auto">
        {/* Project Sub-bar with Slicer Trigger & Batch Polish */}
        <div className="flex flex-wrap items-center justify-between gap-4 bg-zinc-900/60 border border-zinc-800 p-4 rounded-2xl">
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-white tracking-tight">
              {selectedProject ? selectedProject.name : "Select or create a project"}
            </h1>
            <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
              {selectedProject?.aspect_ratio || "16:9"}
            </span>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
              {selectedProject?.shots?.length || 0} Shots
            </span>
            {selectedProject?.default_lut && (
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-emerald-950 text-emerald-300 border border-emerald-700/60">
                LUT: {selectedProject.default_lut}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setShowSlicerDrawer(!showSlicerDrawer)}
              className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-zinc-950 font-bold rounded-xl text-xs transition shadow-lg shadow-amber-500/10"
            >
              <Scissors className="w-4 h-4" />
              <span>3x3 Contact Sheet Slicer</span>
            </button>

            <button
              onClick={handlePolishAll}
              disabled={comfyStatus.is_busy}
              className="flex items-center space-x-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 font-semibold rounded-xl text-xs transition disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span>Polish All in ComfyUI</span>
            </button>

            <button
              onClick={fetchProjects}
              className="p-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white rounded-xl border border-zinc-700 transition"
              title="Refresh State"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ================= 3x3 SLICER DRAWER ================= */}
        {showSlicerDrawer && (
          <div className="bg-zinc-900 border border-amber-500/30 rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2 text-amber-400 font-semibold text-sm">
                <Scissors className="w-4 h-4" />
                <span>Zero-Credit Contact Sheet Slicer (Nano Banana 2.1)</span>
              </div>
              <button
                onClick={() => setShowSlicerDrawer(false)}
                className="text-zinc-500 hover:text-zinc-300 text-xs font-mono"
              >
                Close [ESC]
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* File Dropzone */}
              <div className="md:col-span-2 border-2 border-dashed border-zinc-700 hover:border-amber-500/50 rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition relative bg-zinc-950/40">
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      const f = e.target.files[0];
                      setSlicerFile(f);
                      setSlicerPreview(URL.createObjectURL(f));
                    }
                  }}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />

                {slicerPreview ? (
                  <div className="relative w-full max-h-80 overflow-hidden rounded-lg flex items-center justify-center">
                    <img src={slicerPreview} alt="Grid Preview" className="max-h-80 object-contain rounded" />
                    {/* Visual Grid Overlay */}
                    <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 pointer-events-none border border-amber-400/50">
                      {[...Array(9)].map((_, i) => (
                        <div key={i} className="border border-amber-400/40 flex items-center justify-center">
                          <span className="bg-zinc-900/80 text-amber-300 font-mono text-[10px] px-1 rounded">
                            Shot {i + 1}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <UploadCloud className="w-10 h-10 text-zinc-500 mx-auto" />
                    <p className="text-sm font-medium text-zinc-300">
                      Drag & drop your 3x3 (or 2x2) Nano Banana 2.1 Contact Sheet PNG here
                    </p>
                    <p className="text-xs text-zinc-500">
                      Auto-slices into 9 independent frames without border bleed
                    </p>
                  </div>
                )}
              </div>

              {/* Slicer Settings */}
              <div className="space-y-4 bg-zinc-950/60 p-4 rounded-xl border border-zinc-800 flex flex-col justify-between">
                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-medium text-zinc-400">Grid Dimensions</label>
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <button
                        onClick={() => {
                          setGridRows(3);
                          setGridCols(3);
                        }}
                        className={`py-1.5 text-xs font-semibold rounded-lg border transition ${
                          gridRows === 3
                            ? "bg-amber-500/20 text-amber-300 border-amber-500"
                            : "bg-zinc-800 text-zinc-400 border-zinc-700"
                        }`}
                      >
                        3 x 3 (9 Shots)
                      </button>
                      <button
                        onClick={() => {
                          setGridRows(2);
                          setGridCols(2);
                        }}
                        className={`py-1.5 text-xs font-semibold rounded-lg border transition ${
                          gridRows === 2
                            ? "bg-amber-500/20 text-amber-300 border-amber-500"
                            : "bg-zinc-800 text-zinc-400 border-zinc-700"
                        }`}
                      >
                        2 x 2 (4 Shots)
                      </button>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs text-zinc-400 mb-1">
                      <span>Inner Gutter Trim</span>
                      <span className="font-mono text-amber-400">{gutterPct.toFixed(1)}%</span>
                    </div>
                    <input
                      type="range"
                      min="0.0"
                      max="3.0"
                      step="0.1"
                      value={gutterPct}
                      onChange={(e) => setGutterPct(parseFloat(e.target.value))}
                      className="w-full accent-amber-500 cursor-pointer"
                    />
                    <p className="text-[10px] text-zinc-500 mt-1">
                      Shaves border pixels off each cell edge to prevent black/white grid lines from leaking into Flow.
                    </p>
                  </div>
                </div>

                <button
                  onClick={handleSliceGrid}
                  disabled={!slicerFile || isSlicing}
                  className="w-full py-2.5 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded-xl text-xs transition disabled:opacity-50 flex items-center justify-center space-x-2"
                >
                  <Scissors className="w-4 h-4" />
                  <span>{isSlicing ? "Slicing Grid..." : "Slice into Shots"}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================= STORYBOARD SHOT GRID ================= */}
        {selectedProject && (!selectedProject.shots || selectedProject.shots.length === 0) ? (
          <div className="flex flex-col items-center justify-center py-20 border border-dashed border-zinc-800 rounded-3xl space-y-4 text-center">
            <Film className="w-12 h-12 text-zinc-600" />
            <h3 className="text-lg font-semibold text-zinc-300">No Shots In This Project Yet</h3>
            <p className="text-sm text-zinc-500 max-w-md">
              Slice a contact sheet above, or click <strong>Import Gemini JSON</strong> to paste your shot list.
            </p>
            <div className="flex items-center space-x-3 pt-2">
              <button
                onClick={() => setShowSlicerDrawer(true)}
                className="px-4 py-2 bg-amber-500 text-zinc-950 font-bold rounded-xl text-xs hover:bg-amber-400 transition"
              >
                Upload 3x3 Grid
              </button>
              <button
                onClick={() => setShowImportModal(true)}
                className="px-4 py-2 bg-zinc-800 text-zinc-200 border border-zinc-700 rounded-xl text-xs hover:bg-zinc-700 transition"
              >
                Import Shot JSON
              </button>
            </div>
          </div>
        ) : (
          <div
            className={`grid grid-cols-1 ${
              isVertical
                ? "sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4"
                : "md:grid-cols-2 lg:grid-cols-3"
            } gap-6`}
          >
            {selectedProject?.shots?.map((shot) => {
              const currentMode =
                viewModes[shot.id] ||
                (shot.flow_video_raw ? "video" : shot.polished_start_frame ? "polished" : "start");
              const isAwaiting = shot.status === "awaiting_download";
              const isPolishing = shot.status === "polishing";

              return (
                <div
                  key={shot.id}
                  className={`flex flex-col bg-zinc-900/90 rounded-2xl border transition duration-200 overflow-hidden relative ${
                    isAwaiting
                      ? "border-amber-500 shadow-xl shadow-amber-500/20 ring-2 ring-amber-500/50 animate-pulse"
                      : "border-zinc-800 hover:border-zinc-700"
                  }`}
                >
                  {/* Card Header */}
                  <div className="p-3.5 border-b border-zinc-800/80 flex items-center justify-between bg-zinc-950/40">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400 font-bold border border-amber-500/20">
                        #{shot.shot_number}
                      </span>
                      <span className="text-xs font-semibold text-zinc-200 truncate max-w-[140px]" title={shot.scene_title}>
                        {shot.scene_title || `Shot ${shot.shot_number}`}
                      </span>
                    </div>

                    <div className="flex items-center space-x-1.5">
                      {shot.camera_move && (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700 truncate max-w-[90px]">
                          {shot.camera_move}
                        </span>
                      )}
                      <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                          shot.status === "completed"
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : isAwaiting
                            ? "bg-amber-950 text-amber-300 border border-amber-800"
                            : isPolishing
                            ? "bg-purple-950 text-purple-300 border border-purple-800"
                            : "bg-zinc-800 text-zinc-400"
                        }`}
                      >
                        {shot.status === "completed"
                          ? "Ready"
                          : isAwaiting
                          ? "Awaiting MP4"
                          : isPolishing
                          ? "Polishing..."
                          : shot.status}
                      </span>
                    </div>
                  </div>

                  {/* Voiceover Script Pill for Christian YouTube Narratives */}
                  {shot.voiceover_line && (
                    <div className="px-3.5 py-2 bg-amber-950/20 border-b border-amber-500/20 text-[11px] space-y-0.5">
                      <div className="flex items-center space-x-1 text-amber-400 font-bold uppercase tracking-wider text-[9px]">
                        <Volume2 className="w-3 h-3" />
                        <span>Voiceover Script ({shot.duration_seconds || 6}s):</span>
                      </div>
                      <p className="text-amber-100/90 font-serif italic leading-relaxed line-clamp-3">
                        "{shot.voiceover_line}"
                      </p>
                    </div>
                  )}

                  {/* Media Viewport (Adaptive 9:16 or 16:9) */}
                  <div
                    className={`relative ${
                      isVertical ? "aspect-[9/16] max-h-[380px]" : "aspect-video"
                    } bg-zinc-950 flex items-center justify-center overflow-hidden group`}
                  >
                    {currentMode === "video" && shot.flow_video_raw ? (
                      <video
                        src={`${API_BASE}/media/${selectedProject.slug}/${shot.flow_video_raw}`}
                        controls
                        className="w-full h-full object-cover"
                      />
                    ) : currentMode === "polished" && shot.polished_start_frame ? (
                      <img
                        src={`${API_BASE}/media/${selectedProject.slug}/${shot.polished_start_frame}`}
                        alt="Polished Keyframe"
                        className="w-full h-full object-cover"
                      />
                    ) : currentMode === "end" && shot.raw_end_frame ? (
                      <img
                        src={`${API_BASE}/media/${selectedProject.slug}/${shot.raw_end_frame}`}
                        alt="End Frame"
                        className="w-full h-full object-cover"
                      />
                    ) : shot.raw_start_frame ? (
                      <img
                        src={`${API_BASE}/media/${selectedProject.slug}/${shot.raw_start_frame}`}
                        alt="Start Frame"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center text-zinc-600 space-y-1">
                        <Film className="w-8 h-8 opacity-40" />
                        <span className="text-[11px]">No Frame Sliced</span>
                      </div>
                    )}

                    {/* View Switcher Pills */}
                    <div className="absolute bottom-2 left-2 flex items-center space-x-1 bg-zinc-950/85 backdrop-blur-sm p-0.5 rounded-lg border border-zinc-800 text-[10px]">
                      <button
                        onClick={() => setViewModes({ ...viewModes, [shot.id]: "start" })}
                        className={`px-1.5 py-0.5 rounded transition ${
                          currentMode === "start"
                            ? "bg-amber-500 text-zinc-950 font-bold"
                            : "text-zinc-400 hover:text-white"
                        }`}
                        title="View Start Frame"
                      >
                        Start
                      </button>

                      {shot.raw_end_frame && (
                        <button
                          onClick={() => setViewModes({ ...viewModes, [shot.id]: "end" })}
                          className={`px-1.5 py-0.5 rounded transition ${
                            currentMode === "end"
                              ? "bg-amber-400 text-zinc-950 font-bold"
                              : "text-zinc-400 hover:text-white"
                          }`}
                          title="View End Frame (First & Last Frame Mode)"
                        >
                          End
                        </button>
                      )}

                      <button
                        onClick={() => setViewModes({ ...viewModes, [shot.id]: "polished" })}
                        disabled={!shot.polished_start_frame}
                        className={`px-1.5 py-0.5 rounded transition disabled:opacity-30 ${
                          currentMode === "polished"
                            ? "bg-purple-500 text-white font-bold"
                            : "text-zinc-400 hover:text-white"
                        }`}
                        title="View ComfyUI Polished Keyframe"
                      >
                        Polish
                      </button>
                      <button
                        onClick={() => setViewModes({ ...viewModes, [shot.id]: "video" })}
                        disabled={!shot.flow_video_raw}
                        className={`px-1.5 py-0.5 rounded transition disabled:opacity-30 ${
                          currentMode === "video"
                            ? "bg-emerald-500 text-zinc-950 font-bold"
                            : "text-zinc-400 hover:text-white"
                        }`}
                        title="View Rendered Flow Video"
                      >
                        Video
                      </button>
                    </div>

                    {/* Extracted Last Frame Continuity Badge */}
                    {shot.extracted_last_frame && (
                      <div
                        className="absolute top-2 right-2 flex items-center space-x-1 bg-emerald-950/90 text-emerald-300 border border-emerald-700/60 px-2 py-0.5 rounded-md text-[10px] font-mono shadow-sm"
                        title="Final frame extracted for continuous shot chaining"
                      >
                        <Check className="w-3 h-3" />
                        <span>Chained</span>
                      </div>
                    )}
                  </div>

                  {/* Shot Details & Prompts */}
                  <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                    <div className="space-y-2">
                      {/* Flow Model & Credit Indicator */}
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400 text-[11px]">Flow Engine:</span>
                        <span className="font-mono text-zinc-300 text-[11px] bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700">
                          {shot.flow_model || "veo_3_1_fast"} ({shot.estimated_credits || 15}c) • {shot.duration_seconds || 6}s
                        </span>
                      </div>

                      {/* Prompts Readout */}
                      {shot.motion_prompt && (
                        <div className="bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800/80 text-[11px] space-y-1">
                          <span className="text-[10px] font-bold text-amber-400 tracking-wider uppercase block">
                            Flow Motion Prompt:
                          </span>
                          <p className="text-zinc-300 line-clamp-3 leading-relaxed">{shot.motion_prompt}</p>
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="space-y-2 pt-2 border-t border-zinc-800/60">
                      <div className="grid grid-cols-2 gap-2">
                        {/* Continuity Chaining */}
                        {shot.shot_number > 1 && (
                          <button
                            onClick={() => handleUsePrevLastFrame(shot.id)}
                            className="flex items-center justify-center space-x-1 py-1.5 px-2 bg-zinc-800 hover:bg-zinc-750 text-zinc-300 hover:text-white rounded-lg text-[11px] font-medium border border-zinc-700 transition"
                            title="Set this shot's start frame to previous shot's extracted final frame"
                          >
                            <RotateCcw className="w-3 h-3 text-cyan-400" />
                            <span>Chain Prev</span>
                          </button>
                        )}

                        {/* Polish Keyframe */}
                        <button
                          onClick={() => handlePolishShot(shot.id)}
                          disabled={!shot.raw_start_frame || isPolishing || comfyStatus.is_busy}
                          className={`flex items-center justify-center space-x-1 py-1.5 px-2 bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 border border-purple-800/60 rounded-lg text-[11px] font-medium transition disabled:opacity-30 ${
                            shot.shot_number === 1 ? "col-span-2" : ""
                          }`}
                        >
                          <Sparkles className="w-3 h-3 text-purple-400" />
                          <span>{isPolishing ? "Polishing..." : "Polish ComfyUI"}</span>
                        </button>
                      </div>

                      {/* Flow Handoff CTA */}
                      <button
                        onClick={() => handlePrepForFlow(shot)}
                        className={`w-full py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-2 shadow-md ${
                          copiedShotId === shot.id
                            ? "bg-emerald-500 text-zinc-950"
                            : isAwaiting
                            ? "bg-amber-500 hover:bg-amber-400 text-zinc-950 shadow-amber-500/20"
                            : "bg-zinc-100 hover:bg-white text-zinc-950"
                        }`}
                      >
                        {copiedShotId === shot.id ? (
                          <>
                            <Check className="w-4 h-4" />
                            <span>Copied Prompt & Opened Folder!</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-4 h-4" />
                            <span>Copy Prompt & Reveal Keyframes</span>
                          </>
                        )}
                      </button>

                      {/* Manual Upload Fallback for Drag & Drop */}
                      <div className="flex items-center justify-between pt-1 text-[10px] text-zinc-500">
                        <span>Auto-detecting ~/Downloads...</span>
                        <label className="text-zinc-400 hover:text-amber-400 cursor-pointer underline">
                          Manual upload .mp4
                          <input
                            type="file"
                            accept="video/mp4"
                            className="hidden"
                            onChange={(e) => {
                              if (e.target.files && e.target.files[0]) {
                                handleManualAttachClip(shot.id, e.target.files[0]);
                              }
                            }}
                          />
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* ================= TIMELINE & MASTER EXPORT FOOTER ================= */}
      <footer className="sticky bottom-0 z-30 bg-zinc-900/95 border-t border-zinc-800 backdrop-blur-md px-6 py-4">
        <div className="max-w-[1800px] mx-auto flex flex-wrap items-center justify-between gap-4">
          {/* Timeline Sequence Preview */}
          <div className="flex items-center space-x-3">
            <span className="text-xs font-bold uppercase text-zinc-400 flex items-center space-x-1.5">
              <Film className="w-4 h-4 text-amber-500" />
              <span>Timeline:</span>
            </span>

            <div className="flex items-center space-x-1.5 overflow-x-auto max-w-md py-1">
              {selectedProject?.shots?.map((shot) => (
                <div
                  key={shot.id}
                  className={`w-9 h-6 rounded flex items-center justify-center font-mono text-[10px] font-bold border transition ${
                    shot.flow_video_raw
                      ? "bg-emerald-950 border-emerald-600 text-emerald-300"
                      : "bg-zinc-800 border-zinc-700 text-zinc-500"
                  }`}
                  title={`Shot ${shot.shot_number}: ${shot.flow_video_raw ? "Video Ready" : "Pending"}`}
                >
                  {shot.shot_number}
                </div>
              ))}
            </div>
          </div>

          {/* Master Post-Production Settings */}
          <div className="flex items-center space-x-6">
            {/* LUT Selector */}
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-zinc-400 font-medium">Master LUT:</span>
              <select
                value={selectedProject?.default_lut || "none"}
                onChange={(e) => handleUpdateProjectSetting("default_lut", e.target.value)}
                className="bg-zinc-800 text-zinc-200 rounded-lg px-2.5 py-1 border border-zinc-700 text-xs focus:outline-none"
              >
                {luts.map((l) => (
                  <option key={l} value={l}>
                    {l === "none" ? "None (Pass-through)" : l}
                  </option>
                ))}
              </select>
            </div>

            {/* AI Handle Trim Controls */}
            <div className="flex items-center space-x-3 text-xs text-zinc-400">
              <div className="flex items-center space-x-1.5">
                <span>Trim Start:</span>
                <input
                  type="number"
                  min="0"
                  max="12"
                  value={selectedProject?.trim_start_frames || 4}
                  onChange={(e) => handleUpdateProjectSetting("trim_start_frames", parseInt(e.target.value))}
                  className="w-12 bg-zinc-800 text-zinc-200 text-center rounded py-0.5 border border-zinc-700 text-xs"
                />
                <span className="text-[10px] text-zinc-500">frames</span>
              </div>

              <div className="flex items-center space-x-1.5">
                <span>Trim End:</span>
                <input
                  type="number"
                  min="0"
                  max="12"
                  value={selectedProject?.trim_end_frames || 4}
                  onChange={(e) => handleUpdateProjectSetting("trim_end_frames", parseInt(e.target.value))}
                  className="w-12 bg-zinc-800 text-zinc-200 text-center rounded py-0.5 border border-zinc-700 text-xs"
                />
                <span className="text-[10px] text-zinc-500">frames</span>
              </div>
            </div>

            {/* Assemble Master Cut Button */}
            <button
              onClick={handleAssembleMasterCut}
              disabled={isAssembling || comfyStatus.is_busy}
              className="flex items-center space-x-2 px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-zinc-950 font-bold rounded-xl text-xs transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              <Video className="w-4 h-4" />
              <span>{isAssembling ? "Assembling Cut..." : "Assemble Master Cut"}</span>
            </button>
          </div>
        </div>
      </footer>

      {/* ================= MODAL: CREATE PROJECT ================= */}
      {showNewProjectModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white">Create New Video Project</h3>
            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Project Name</label>
                <input
                  type="text"
                  placeholder="e.g. Genesis: The Creation Week"
                  value={newProjectName}
                  onChange={(e) => {
                    setNewProjectName(e.target.value);
                    if (!newProjectSlug) {
                      setNewProjectSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "_"));
                    }
                  }}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1">Aspect Ratio</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setNewProjectAspect("9:16")}
                    className={`py-2 text-xs font-semibold rounded-xl border transition ${
                      newProjectAspect === "9:16"
                        ? "bg-amber-500/20 text-amber-300 border-amber-500"
                        : "bg-zinc-950 text-zinc-400 border-zinc-800"
                    }`}
                  >
                    9:16 (Vertical Shorts)
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewProjectAspect("16:9")}
                    className={`py-2 text-xs font-semibold rounded-xl border transition ${
                      newProjectAspect === "16:9"
                        ? "bg-amber-500/20 text-amber-300 border-amber-500"
                        : "bg-zinc-950 text-zinc-400 border-zinc-800"
                    }`}
                  >
                    16:9 (Landscape Doc)
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1">Folder Slug</label>
                <input
                  type="text"
                  placeholder="e.g. genesis_creation_vertical"
                  value={newProjectSlug}
                  onChange={(e) => setNewProjectSlug(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-sm font-mono text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewProjectModal(false)}
                  className="px-4 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded-xl text-xs transition"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ================= MODAL: IMPORT GEMINI SHOT JSON ================= */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-xl w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center space-x-2">
                <FileText className="w-5 h-5 text-cyan-400" />
                <span>Import Gemini 4 Argon Shot JSON</span>
              </h3>
              <button onClick={() => setShowImportModal(false)} className="text-zinc-500 hover:text-white text-xs">
                ✕
              </button>
            </div>

            <p className="text-xs text-zinc-400">
              Paste the 9-shot JSON array generated by Gemini 4 Argon. It will automatically populate your Storyboard Shot Cards.
            </p>

            <form onSubmit={handleImportJson} className="space-y-4">
              <textarea
                rows={10}
                placeholder={`[\n  {\n    "shot_number": 1,\n    "scene_title": "Day 0: The Mountainous Abyss",\n    "flow_mode": "frames_first_and_last",\n    "flow_model": "veo_3_1_fast",\n    "voiceover_line": "In the beginning... darkness covered the face of the deep.",\n    "image_prompt": "Hard-mounted surface-skimming IMAX 70mm perspective...",\n    "motion_prompt": "Hard-mounted water-level IMAX camera pushes into...",\n    "camera_move": "hard-mounted low push in"\n  }\n]`}
                value={importJsonText}
                onChange={(e) => setImportJsonText(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs font-mono text-zinc-200 focus:outline-none focus:border-cyan-500"
              />

              {importError && (
                <div className="flex items-center space-x-2 text-rose-400 text-xs">
                  <AlertCircle className="w-4 h-4" />
                  <span>{importError}</span>
                </div>
              )}

              <div className="flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  className="px-4 py-2 text-xs text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-zinc-950 font-bold rounded-xl text-xs transition"
                >
                  Import Shots
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ================= MODAL: GEMINI 4 ARGON PROMPT HELPER ================= */}
      {showPromptHelperModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-2xl w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-amber-400 flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-amber-400" />
                <span>Gemini 4 Argon Pre-Production Prompt</span>
              </h3>
              <button onClick={() => setShowPromptHelperModal(false)} className="text-zinc-500 hover:text-white text-xs">
                ✕
              </button>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed">
              Copy this master prompt into our chat with <strong>Gemini 4 Argon</strong>. Argon will produce your 4K 3x3 contact sheet prompt and the formatted JSON shot list:
            </p>

            <div className="relative bg-zinc-950 rounded-xl p-4 border border-zinc-800 text-xs font-mono text-zinc-300 space-y-2">
              <pre className="whitespace-pre-wrap font-sans text-xs text-zinc-300">
{`Act as my AI Director of Photography for our Christian YouTube Channel. For the following scriptural passage or video concept, produce two outputs:

1. **Nano Banana 2.1 3x3 Contact Sheet Prompt**: A single detailed image generation prompt that renders a 3x3 cinematic storyboard contact sheet (9 sequential frames in one 4K grid) with sacred realism, chiaroscuro lighting, and 65mm / 70mm IMAX film grain.

2. **Flow Companion Shot List JSON**: A JSON array of 9 shot objects matching the 9 grid cells. For each shot, include:
   - "shot_number" (1 to 9)
   - "scene_title"
   - "voiceover_line" (the scriptural narration sentence for this shot)
   - "flow_mode" ("frames_first_and_last" or "frames")
   - "flow_model" ("veo_3_1_fast" or "veo_3_1_lite")
   - "duration_seconds" (4, 6, or 8)
   - "estimated_credits" (5, 10, or 15)
   - "image_prompt" (for local ComfyUI skin/texture polish pass)
   - "motion_prompt" (strictly describing action path and camera movement for Google Flow)
   - "camera_move" (e.g., "slow macro slider", "locked-horizon forward glide")
   - "aspect_ratio" ("9:16" or "16:9")`}
              </pre>

              <button
                onClick={() => {
                  navigator.clipboard.writeText(`Act as my AI Director of Photography for our Christian YouTube Channel. For the following scriptural passage or video concept, produce two outputs:

1. **Nano Banana 2.1 3x3 Contact Sheet Prompt**: A single detailed image generation prompt that renders a 3x3 cinematic storyboard contact sheet (9 sequential frames in one 4K grid) with sacred realism, chiaroscuro lighting, and 65mm / 70mm IMAX film grain.

2. **Flow Companion Shot List JSON**: A JSON array of 9 shot objects matching the 9 grid cells. For each shot, include:
   - "shot_number" (1 to 9)
   - "scene_title"
   - "voiceover_line" (the scriptural narration sentence for this shot)
   - "flow_mode" ("frames_first_and_last" or "frames")
   - "flow_model" ("veo_3_1_fast" or "veo_3_1_lite")
   - "duration_seconds" (4, 6, or 8)
   - "estimated_credits" (5, 10, or 15)
   - "image_prompt" (for local ComfyUI skin/texture polish pass)
   - "motion_prompt" (strictly describing action path and camera movement for Google Flow)
   - "camera_move" (e.g., "slow macro slider", "locked-horizon forward glide")
   - "aspect_ratio" ("9:16" or "16:9")`);
                  alert("Copied to clipboard!");
                }}
                className="absolute top-3 right-3 px-3 py-1 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded-lg text-xs flex items-center space-x-1"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </button>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setShowPromptHelperModal(false)}
                className="px-4 py-2 bg-zinc-800 text-zinc-200 rounded-xl text-xs hover:bg-zinc-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: MASTER CUT PLAYBACK ================= */}
      {showMasterCutModal && masterCutUrl && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-emerald-500/40 rounded-2xl p-6 max-w-4xl w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2 text-emerald-400 font-bold">
                <Video className="w-5 h-5" />
                <span>Master Cut Assembled (FFmpeg + {selectedProject?.default_lut || "LUT"})</span>
              </div>
              <button onClick={() => setShowMasterCutModal(false)} className="text-zinc-500 hover:text-white text-xs">
                ✕
              </button>
            </div>

            <div
              className={`bg-black rounded-xl overflow-hidden shadow-inner flex items-center justify-center ${
                isVertical ? "aspect-[9/16] max-h-[500px] mx-auto" : "aspect-video"
              }`}
            >
              <video src={masterCutUrl} controls autoPlay className="w-full h-full object-contain" />
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-zinc-400">
                AI start/end handles trimmed & graded with {selectedProject?.default_lut}. Timeline manifest exported.
              </span>
              <div className="flex items-center space-x-3">
                <a
                  href={masterCutUrl}
                  download="master_cut.mp4"
                  className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold rounded-xl text-xs flex items-center space-x-1.5 transition"
                >
                  <Download className="w-4 h-4" />
                  <span>Download MP4</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

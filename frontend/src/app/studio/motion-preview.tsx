"use client";
import { useEffect, useId, useRef, useState } from "react";

type Vec = [number, number, number];
const descriptions: Record<string, string> = {
  locked: "Camera stays fixed. The subject walks across the frame.",
  dolly: "Camera moves toward the subject. Foreground and background shift at different rates.",
  out: "Camera moves away from the subject, revealing more of the environment.",
  tracking: "Camera and subject travel together. Background slides behind the subject.",
  pan: "Camera rotates horizontally from a fixed position.",
  tilt: "Camera rotates vertically from a fixed position.",
  orbit: "Camera travels around the subject, keeping the subject in view.",
  handheld: "Small changes in camera position and aim create restrained handheld drift.",
};
function movementKey(value: string) {
  const key = value.toLowerCase().replace(/[_ ]/g, "-");
  if (key.includes("out")) return "out";
  if (key.includes("dolly") || key.includes("push")) return "dolly";
  if (key.includes("track") || key.includes("truck")) return "tracking";
  return Object.keys(descriptions).find(k => key.includes(k)) || "locked";
}
function cameraAt(kind: string, t: number): { position: Vec; yaw: number; pitch: number; subject: number } {
  const p = t / 6;
  let position: Vec = [0, 1.6, -7], yaw = 0, pitch = -.025, subject = 0;
  if (kind === "dolly") position = [0, 1.6, -9 + p * 5];
  if (kind === "out") position = [0, 1.6, -4 - p * 5];
  if (kind === "tracking") { subject = -2 + p * 4; position = [subject, 1.6, -7]; }
  if (kind === "locked") subject = -2 + p * 4;
  if (kind === "pan") yaw = -.26 + p * .52;
  if (kind === "tilt") pitch = -.22 + p * .44;
  if (kind === "orbit") { const a = -.65 + p * 1.3; position = [Math.sin(a) * 7, 1.6, -Math.cos(a) * 7]; yaw = -a; }
  if (kind === "handheld") { position = [Math.sin(t * 2.3) * .11, 1.6 + Math.sin(t * 3.1) * .045, -7 + Math.cos(t * 1.7) * .08]; yaw = Math.sin(t * 1.9) * .012; pitch += Math.cos(t * 2.7) * .009; }
  return {position, yaw, pitch, subject};
}

/** A perspective-projected scene, not a transformed still or a prediction of generated footage. */
export function MotionPreview({ variant, name }: { variant: string; name?: string }) {
  const kind = movementKey(variant);
  const [time, setTime] = useState(0), [playing, setPlaying] = useState(false), [reduced, setReduced] = useState(false);
  const current = useRef(0);
  const id = useId().replaceAll(":", "");
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!media) return;
    const update = () => { setReduced(media.matches); if (media.matches) setPlaying(false); };
    update(); media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);
  useEffect(() => { setPlaying(false); setTime(0); current.current = 0; }, [variant]);
  useEffect(() => {
    if (!playing || reduced) return;
    let previous = performance.now(), frame: number;
    const tick = (now: number) => {
      const next = Math.min(6, current.current + (now - previous) / 1000);
      previous = now; current.current = next; setTime(next);
      if (next >= 6) setPlaying(false);
      else frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [playing, reduced]);
  const camera = cameraAt(kind, time);
  const project = ([x, y, z]: Vec) => {
    const dx = x - camera.position[0], dy = y - camera.position[1], dz = z - camera.position[2];
    const xx = dx * Math.cos(camera.yaw) - dz * Math.sin(camera.yaw);
    const depth = dx * Math.sin(camera.yaw) + dz * Math.cos(camera.yaw);
    const yy = dy * Math.cos(camera.pitch) - depth * Math.sin(camera.pitch);
    const zz = Math.max(.3, dy * Math.sin(camera.pitch) + depth * Math.cos(camera.pitch));
    return [320 + xx * 410 / zz, 180 - yy * 410 / zz, zz];
  };
  const line = (a: Vec, b: Vec, key: string) => { const p = project(a), q = project(b); return <line key={key} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} />; };
  const box = (x: number, y: number, z: number, w: number, h: number, d: number, color: string, key: string) => {
    const points: Vec[] = [[x-w/2,y,z-d/2],[x+w/2,y,z-d/2],[x+w/2,y+h,z-d/2],[x-w/2,y+h,z-d/2],[x-w/2,y,z+d/2],[x+w/2,y,z+d/2],[x+w/2,y+h,z+d/2],[x-w/2,y+h,z+d/2]];
    return <g key={key} stroke="#12161a" strokeWidth="1">{[[4,5,6,7],[1,5,6,2],[0,4,7,3],[3,2,6,7],[0,1,2,3]].map((face,i)=><polygon key={i} points={face.map(index=>project(points[index]).slice(0,2).join(",")).join(" ")} fill={color} fillOpacity={.5+i*.1} />)}</g>;
  };
  const head = project([camera.subject, 1.92, 0]);
  const map = (p: Vec) => [64 + p[0] * 6, 15 - p[2] * 6];
  const path = Array.from({length:25},(_,i)=>map(cameraAt(kind,i/4).position).join(",")).join(" ");
  const point = map(camera.position);
  return <figure className="cl-motion">
    <div className="cl-motion-scene">
      <svg viewBox="0 0 640 360" role="img" aria-label="Camera view spatial demonstration">
        <defs><linearGradient id={`room-${id}`} x2="0" y2="1"><stop stopColor="#242d35"/><stop offset="1" stopColor="#111419"/></linearGradient></defs>
        <rect width="640" height="360" fill={`url(#room-${id})`}/>
        <g stroke="#69747d" strokeOpacity=".27">{Array.from({length:13},(_,i)=>line([i-6,0,-2],[i-6,0,12],`x${i}`))}{Array.from({length:15},(_,i)=>line([-8,0,i-2],[8,0,i-2],`z${i}`))}</g>
        {[-4,-2,2,4].map((x,i)=>box(x,0,7,.3,4,.3,"#56616a",`pillar${i}`))}
        {box(2.5,0,3,1.5,.65,1,"#6b7169","bench")}
        {box(camera.subject,0,0,.52,1.56,.35,"#b96a3d","subject")}
        <circle cx={head[0]} cy={head[1]} r={.23*410/head[2]} fill="#e5c0a2"/>
        {box(-2.1,0,-2,.6,.9,.6,"#596b70","foreground")}
        <g stroke="#eee0d0" opacity=".45" fill="none"><path d="M22 45V22H45M595 22H618V45M22 315V338H45M595 338H618V315"/><path d="M310 180H330M320 170V190" strokeWidth=".7"/></g>
        <text x="25" y="325" fill="#c5cbd0" fontSize="10" letterSpacing="2">PERSPECTIVE VIEW · FIXED FIELD OF VIEW</text>
      </svg>
      <svg className="cl-path-map" viewBox="0 0 128 80" role="img" aria-label="Camera path plan view">
        <rect width="128" height="80" rx="8" fill="#101418" fillOpacity=".88"/>
        <polyline points={path} fill="none" stroke="#f4a16c" strokeDasharray="3 2"/>
        <circle cx={64+camera.subject*6} cy="15" r="3" fill="#e5c0a2"/>
        <circle cx={point[0]} cy={point[1]} r="4" fill="#f4a16c"/>
        <line x1={point[0]} y1={point[1]} x2={point[0]+Math.sin(camera.yaw)*15} y2={point[1]-Math.cos(camera.yaw)*15} stroke="#f4a16c"/>
        <text x="8" y="73" fill="#c5cbd0" fontSize="7">CAMERA PATH · TOP VIEW</text>
      </svg>
      <span className="cl-media-tag">Spatial demonstration</span>
    </div>
    <div className="cl-transport"><button type="button" disabled={reduced} onClick={()=>{if(time>=6){current.current=0;setTime(0);}setPlaying(!playing);}}>{playing?"Pause":"Play"}</button><input aria-label="Scrub camera demonstration" type="range" min="0" max="6" step=".01" value={time} onChange={e=>{setPlaying(false);current.current=Number(e.target.value);setTime(Number(e.target.value));}}/><output>{time.toFixed(1)} / 6s</output></div>
    <figcaption><strong>{name || kind} · spatial demonstration</strong><span>{descriptions[kind]}</span><span>Camera ({camera.position.map(n=>n.toFixed(1)).join(", ")}) m · Subject {camera.subject.toFixed(1)} m{reduced?" · Reduced motion: use the scrubber":""}</span></figcaption>
  </figure>;
}

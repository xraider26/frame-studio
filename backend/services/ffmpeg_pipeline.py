import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import List, Optional

def extract_last_frame(video_path: str, output_png_path: str) -> str:
    """
    Extracts the exact final frame of a Flow clip to use as the Start Frame of the next shot
    for seamless continuity chaining.
    """
    out_path = Path(output_png_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-sseof",
        "-0.05",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "1",
        str(output_png_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        duration = get_video_duration(video_path)
        seek_point = max(0.0, duration - 0.05)
        cmd_fallback = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{seek_point:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "1",
            str(output_png_path),
        ]
        subprocess.run(cmd_fallback, check=True, capture_output=True)

    return str(output_png_path)

def get_video_duration(video_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    probe = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(probe.stdout.strip())

def has_audio_stream(video_path: str) -> bool:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    probe = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return bool(probe.stdout.strip())

def trim_and_grade_clip(
    input_video: str,
    output_video: str,
    trim_start_sec: float = 0.16,  # ~4 frames at 24fps
    trim_end_sec: float = 0.16,
    lut_path: Optional[str] = None,
    is_vertical: bool = False,
) -> str:
    """
    Trims dead AI static start/end handles, scales to vertical 1080x1920 or 1920x1080,
    and applies a unifying master 3D LUT (e.g., primeval_imax_65mm.cube).
    Generates silent audio track if clip has none so concat never fails.
    """
    out_path = Path(output_video)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(input_video)
    keep_duration = max(0.5, duration - trim_start_sec - trim_end_sec)

    scale_filter = "scale=1080:1920:flags=lanczos" if is_vertical else "scale=1920:1080:flags=lanczos"
    vf_filters = [scale_filter, "fps=24"]

    local_lut_copy = None
    if lut_path and Path(lut_path).exists():
        # Copy LUT to temporary filename in out_path.parent so Windows path with colons never breaks FFmpeg filter
        local_lut_copy = out_path.parent / "_temp_grade.cube"
        shutil.copyfile(lut_path, local_lut_copy)
        vf_filters.append(f"lut3d=file='{local_lut_copy.as_posix()}'")

    vf_filters.append("format=yuv420p")

    try:
        if has_audio_stream(input_video):
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", f"{trim_start_sec:.3f}",
                "-i", str(input_video),
                "-t", f"{keep_duration:.3f}",
                "-vf", ",".join(vf_filters),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "17",
                "-c:a", "aac",
                "-ar", "48000",
                "-ac", "2",
                "-b:a", "192k",
                "-threads", "4",
                str(output_video),
            ]
        else:
            # Generate silent stereo track if video has no native audio
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", f"{trim_start_sec:.3f}",
                "-i", str(input_video),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t", f"{keep_duration:.3f}",
                "-vf", ",".join(vf_filters),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "17",
                "-c:a", "aac",
                "-b:a", "192k",
                "-threads", "4",
                str(output_video),
            ]
        subprocess.run(cmd, check=True, capture_output=True)
    finally:
        if local_lut_copy and local_lut_copy.exists():
            local_lut_copy.unlink(missing_ok=True)

    return str(output_video)

def assemble_master_cut(
    shot_video_paths: List[str],
    output_master_path: str,
    trim_start_frames: int = 4,
    trim_end_frames: int = 4,
    lut_path: Optional[str] = None,
    voiceover_path: Optional[str] = None,
    is_vertical: bool = False,
    fps: int = 24,
) -> str:
    """
    Trims, scales, and grades all clips, concats them, and optionally ducks environmental
    audio beneath an uploaded voiceover track via sidechain compression.
    """
    out_master = Path(output_master_path)
    out_master.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = out_master.parent / "temp_trimmed"
    temp_dir.mkdir(parents=True, exist_ok=True)

    trim_start_sec = trim_start_frames / fps
    trim_end_sec = trim_end_frames / fps

    trimmed_paths = []
    for idx, raw_path in enumerate(shot_video_paths, start=1):
        if not Path(raw_path).exists():
            continue
        dest_trimmed = temp_dir / f"trimmed_shot_{idx:02d}.mp4"
        trim_and_grade_clip(
            input_video=raw_path,
            output_video=str(dest_trimmed),
            trim_start_sec=trim_start_sec,
            trim_end_sec=trim_end_sec,
            lut_path=lut_path,
            is_vertical=is_vertical,
        )
        trimmed_paths.append(dest_trimmed)

    if not trimmed_paths:
        raise ValueError("No valid video clips found to assemble.")

    # Concat list file
    concat_txt = temp_dir / "concat_list.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in trimmed_paths:
            f.write(f"file '{p.resolve().as_posix()}'\n")

    stitched_no_vo = temp_dir / "_stitched_visuals.mp4"
    cmd_concat = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_txt),
        "-c", "copy",
        str(stitched_no_vo),
    ]
    subprocess.run(cmd_concat, check=True, capture_output=True)

    # Optional Voiceover Audio-Ducking Pipeline
    if voiceover_path and Path(voiceover_path).exists():
        filter_complex = (
            "[0:a]volume=0.85[bg];"
            "[1:a]highpass=f=75,lowpass=f=12000,acompressor=threshold=-18dB:ratio=3:makeup=4dB,asplit=2[vo_sc][vo_mix];"
            "[bg][vo_sc]sidechaincompress=threshold=0.025:ratio=6:attack=40:release=450[bg_ducked];"
            "[bg_ducked][vo_mix]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[a_out]"
        )
        cmd_mix = [
            "ffmpeg",
            "-y",
            "-i", str(stitched_no_vo),
            "-i", str(voiceover_path),
            "-filter_complex", filter_complex,
            "-map", "0:v:0", "-map", "[a_out]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "256k",
            str(out_master),
        ]
        subprocess.run(cmd_mix, check=True, capture_output=True)
    else:
        shutil.copyfile(stitched_no_vo, out_master)

    shutil.rmtree(temp_dir, ignore_errors=True)

    # Generate companion timeline JSON manifest
    manifest_path = out_master.with_suffix(".timeline.json")
    timeline_meta = {
        "project_export": out_master.name,
        "aspect_ratio": "9:16" if is_vertical else "16:9",
        "fps": fps,
        "total_clips": len(trimmed_paths),
        "lut_applied": Path(lut_path).name if lut_path else "none",
        "voiceover_mixed": bool(voiceover_path and Path(voiceover_path).exists()),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(timeline_meta, f, indent=2)

    return str(out_master)

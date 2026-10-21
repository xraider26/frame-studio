import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

class DownloadsWatcherHandler(FileSystemEventHandler):
    def __init__(self, on_video_detected: Callable[[str], None]):
        super().__init__()
        self.on_video_detected = on_video_detected
        self.processed_files = set()

    def on_created(self, event):
        if event.is_directory:
            return
        self._check_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._check_file(event.src_path)

    def _check_file(self, file_path_str: str):
        path = Path(file_path_str)
        if path.suffix.lower() == ".mp4" and not path.name.startswith("."):
            if str(path) in self.processed_files:
                return

            # Wait briefly for browser download stream to complete
            file_ready = self._wait_until_file_stable(path)
            if file_ready and str(path) not in self.processed_files:
                self.processed_files.add(str(path))
                self.on_video_detected(str(path))

    def _wait_until_file_stable(self, path: Path, max_attempts: int = 25, delay: float = 0.4) -> bool:
        last_size = -1
        for _ in range(max_attempts):
            if not path.exists():
                return False
            # Check for partial download companion files (e.g. .crdownload)
            crdownload = path.with_name(path.name + ".crdownload")
            if crdownload.exists():
                time.sleep(delay)
                continue
            try:
                curr_size = path.stat().st_size
                if curr_size > 0 and curr_size == last_size:
                    # Verify file can be opened for read exclusively
                    with open(path, "rb"):
                        return True
                last_size = curr_size
            except (PermissionError, OSError):
                pass
            time.sleep(delay)
        return path.exists() and path.stat().st_size > 0


class FlowDownloadsWatcher:
    def __init__(self, watch_dir: Optional[str] = None):
        self.watch_dir = Path(watch_dir or os.path.expanduser("~/Downloads"))
        self.observer: Optional[Observer] = None
        self.is_running = False
        self.callback: Optional[Callable[[str], None]] = None

    def start(self, on_video_detected: Callable[[str], None]):
        if self.is_running:
            return
        self.callback = on_video_detected
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        handler = DownloadsWatcherHandler(self._handle_detected)
        self.observer = Observer()
        self.observer.schedule(handler, str(self.watch_dir), recursive=False)
        self.observer.start()
        self.is_running = True
        print(f"[Watcher] Started watching: {self.watch_dir}")

    def _handle_detected(self, file_path: str):
        if self.callback:
            try:
                self.callback(file_path)
            except Exception as e:
                print(f"[Watcher] Error in callback: {e}")

    def stop(self):
        if self.observer and self.is_running:
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            print("[Watcher] Stopped watching.")

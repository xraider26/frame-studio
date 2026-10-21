import asyncio
import copy
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
from PIL import Image, ImageEnhance, ImageFilter

COMFY_HOST = os.getenv("COMFY_HOST", "127.0.0.1:8188")

class ComfySequentialRunner:
    def __init__(self, workflow_template_path: Optional[str] = None):
        if not workflow_template_path:
            workflow_template_path = str(Path(__file__).parent.parent / "workflows" / "polish_api.json")
        self.workflow_path = workflow_template_path
        self.is_busy = False
        self.current_task_info = ""
        self._lock = asyncio.Lock()

    def _load_template(self) -> Dict[str, Any]:
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"http://{COMFY_HOST}/system_stats")
                return res.status_code == 200
        except Exception:
            return False

    async def upload_image_to_comfy(self, image_path: str) -> Optional[str]:
        """Uploads an image to ComfyUI's input directory so LoadImage can find it."""
        try:
            filename = Path(image_path).name
            async with httpx.AsyncClient(timeout=15.0) as client:
                with open(image_path, "rb") as f:
                    files = {"image": (filename, f, "image/png")}
                    data = {"overwrite": "true"}
                    res = await client.post(f"http://{COMFY_HOST}/upload/image", files=files, data=data)
                    if res.status_code == 200:
                        return res.json().get("name", filename)
        except Exception as e:
            print(f"[ComfyUI] Image upload error: {e}")
        return Path(image_path).name

    async def polish_keyframe(
        self,
        input_image_path: str,
        output_image_path: str,
        prompt_text: str = "",
        denoise: float = 0.28,
        seed: Optional[int] = None,
        use_fallback_if_offline: bool = True,
    ) -> Dict[str, Any]:
        """
        Processes a single keyframe sequentially to protect GPU VRAM (RX 9070 XT 16GB limit).
        Enforces batch_size=1 and holds is_busy lock so FFmpeg never competes for system resources.
        """
        async with self._lock:
            self.is_busy = True
            self.current_task_info = f"Polishing {Path(input_image_path).name}"
            try:
                available = await self.is_available()
                if not available:
                    if use_fallback_if_offline:
                        # Graceful offline mode: Applies subtle local enhancement (slight contrast, sharpness, film tone)
                        # so that development, testing, and Flow handoff work even when ComfyUI isn't running.
                        self._apply_offline_enhancement(input_image_path, output_image_path)
                        return {
                            "status": "completed_fallback",
                            "message": "ComfyUI offline; generated enhanced preview pass",
                            "output_path": output_image_path,
                            "seed": seed or 42,
                        }
                    else:
                        raise ConnectionError(f"ComfyUI is not reachable at http://{COMFY_HOST}")

                # 1. Upload source image to ComfyUI
                comfy_image_name = await self.upload_image_to_comfy(input_image_path) or Path(input_image_path).name

                # 2. Inject parameters into workflow
                wf = copy.deepcopy(self._load_template())
                actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)

                if "10" in wf and "inputs" in wf["10"]:
                    wf["10"]["inputs"]["image"] = comfy_image_name
                if "6" in wf and "inputs" in wf["6"]:
                    if prompt_text.strip():
                        wf["6"]["inputs"]["text"] = f"{prompt_text}, cinematic 35mm film grain, sharp texture, photorealistic skin"
                if "3" in wf and "inputs" in wf["3"]:
                    wf["3"]["inputs"]["denoise"] = float(denoise)
                    wf["3"]["inputs"]["seed"] = actual_seed

                # 3. Submit prompt
                client_id = f"flow_companion_{random.randint(1000, 9999)}"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"http://{COMFY_HOST}/prompt",
                        json={"prompt": wf, "client_id": client_id},
                    )
                    resp.raise_for_status()
                    prompt_id = resp.json().get("prompt_id")

                # 4. Wait for execution completion
                output_saved = await self._wait_for_prompt_completion(prompt_id, output_image_path)
                return {
                    "status": "completed",
                    "prompt_id": prompt_id,
                    "seed": actual_seed,
                    "output_path": output_saved or output_image_path,
                }
            finally:
                self.is_busy = False
                self.current_task_info = ""

    async def _wait_for_prompt_completion(self, prompt_id: str, dest_path: str, max_wait_sec: int = 180) -> Optional[str]:
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        start_time = asyncio.get_event_loop().time()

        async with httpx.AsyncClient(timeout=10.0) as client:
            while (asyncio.get_event_loop().time() - start_time) < max_wait_sec:
                try:
                    res = await client.get(f"http://{COMFY_HOST}/history/{prompt_id}")
                    if res.status_code == 200:
                        data = res.json()
                        if prompt_id in data:
                            outputs = data[prompt_id].get("outputs", {})
                            for node_id, node_out in outputs.items():
                                if "images" in node_out and len(node_out["images"]) > 0:
                                    img_info = node_out["images"][0]
                                    fn = img_info["filename"]
                                    subfolder = img_info.get("subfolder", "")
                                    img_type = img_info.get("type", "output")
                                    # Download rendered image
                                    img_res = await client.get(
                                        f"http://{COMFY_HOST}/view",
                                        params={"filename": fn, "subfolder": subfolder, "type": img_type},
                                    )
                                    if img_res.status_code == 200:
                                        with open(dest, "wb") as f_out:
                                            f_out.write(img_res.content)
                                        return str(dest)
                except Exception as e:
                    print(f"[ComfyUI] Poll error: {e}")
                await asyncio.sleep(1.0)
        return None

    def _apply_offline_enhancement(self, input_path: str, output_path: str):
        """Creates an offline enhanced mock keyframe when ComfyUI is not running."""
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(input_path).convert("RGB") as img:
            enhancer = ImageEnhance.Sharpness(img)
            sharp = enhancer.enhance(1.25)
            contrast = ImageEnhance.Contrast(sharp).enhance(1.08)
            contrast.save(dest, format="PNG")

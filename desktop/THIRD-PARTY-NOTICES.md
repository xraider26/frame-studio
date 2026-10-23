# Orchestra bundled software

This beta bundles the existing Orchestra application with Electron/Chromium/Node.js, a frozen Python runtime, its declared Python dependencies, the Next.js standalone runtime, and unmodified FFmpeg/FFprobe tools.

Electron and Chromium notices are included alongside the installed application (`LICENSE.electron.txt`, `LICENSES.chromium.html`). Frozen package notices remain under the service's `_internal` directory where supplied by their distribution. The web runtime retains dependency license files included by Next's traced standalone output.

FFmpeg/FFprobe are standalone command-line programs called by Orchestra. This build uses the Gyan Windows distribution already installed on the build machine. Its original license and README are copied beside the binaries as `FFMPEG-LICENSE.txt` and `FFMPEG-README.txt`. The unmodified build identifies its exact version and configuration through `ffmpeg -version`. Vendor distribution and build/source information: https://www.gyan.dev/ffmpeg/builds/ . FFmpeg source and license information: https://ffmpeg.org/download.html and https://ffmpeg.org/legal.html . Upstream source: https://git.ffmpeg.org/ffmpeg.git . Other linked libraries are identified in the bundled binary's build configuration and vendor README.

No third-party source PDFs, user projects, API credentials or paid generation access are included. Generated teaching images and their exact prompts are shipped as application examples, not as guarantees of model output.

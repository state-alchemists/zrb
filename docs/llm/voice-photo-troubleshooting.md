🔖 [Documentation Home](../../README.md) > [LLM](./) > Voice & Photo Troubleshooting

# Voice & Photo Troubleshooting

`/voice` and `/photo` depend on OS-level microphone/camera access, so failures are usually platform setup, not a zrb bug. Configuration knobs for both features are in [LLM Configuration → Voice and Camera](../configuration/llm-config.md#23-voice-and-camera); the commands themselves are listed under [TUI Commands](llm-integration.md#tui-commands).

---

## Table of Contents

- [Voice (`/voice`)](#voice-voice)
- [Photo (`/photo`)](#photo-photo)
- [WSL2 camera passthrough: building a custom kernel](#wsl2-camera-passthrough-building-a-custom-kernel)

---

## Voice (`/voice`)

| Symptom | Solution |
|---------|----------|
| `/voice` or `/handsfree` says dictation needs the `zrb[voice]` extra | `pip install 'zrb[voice]'` (sounddevice, numpy, vosk, pipecat-ai) |
| An error mentioning `vosk` | vosk is the default backend: install it, or switch `ZRB_LLM_DICTATION_BACKEND` to `openai`/`google`/`multimodal` |
| Hands-free never submits anything | Run `zrb voice mic-test` from `examples/voice-interaction`; if your speech stays under the threshold, lower `ZRB_LLM_DICTATION_THRESHOLD`. With wake words set, only utterances starting with one count |
| In a public place, the room's own conversation becomes turns | Set `ZRB_LLM_DICTATION_WAKE_WORDS`: nothing else tells a stranger's request from yours. `ZRB_LLM_DICTATION_NOISE_MARGIN` (raise it; `0` counts the room not at all) and `ZRB_LLM_DICTATION_MIN_WORDS` (2 or more) keep the room's background and a stray word out |
| Hands-free ignores what you say in a loud room | The bar is over the room: lower `ZRB_LLM_DICTATION_NOISE_MARGIN` (default 2; `0` disables it), lower `ZRB_LLM_DICTATION_MIN_WORDS`, or speak up |
| Hands-free goes quiet after a long sentence | The bar is measured from everything heard while zrb is silent, your own speech included, so a long uninterrupted sentence can sit above your next words until something about a quarter as loud as your voice — a breath or a sentence break — is heard. Lower `ZRB_LLM_DICTATION_NOISE_MARGIN`, or set it to `0` in a quiet room |
| zrb's speech stutters, and it talks on, while you talk over it | On speakers `ZRB_LLM_DICTATION_BARGE_IN_MARGIN` (3) is holding zrb's voice for what it hears of itself: the hold is given back a moment later, which is the price of not waiting for your words. Keep it at 3 and lower the playback volume, or use headphones |
| With wake words set, saying "stop" over zrb does nothing | Anything said over zrb is put to the small model when the word lists cannot read it, so "please fucking stop", "shut up" and a stop in another language stop it too. A stop word said alone is still exact and free, and must be made only of `ZRB_LLM_DICTATION_STOP_WORDS` words; `ZRB_LLM_DICTATION_INTERRUPT_JUDGE_ENABLED=off` leaves the word lists deciding alone |
| With the `vosk` backend, a sentence you said is dropped as too faint | `ZRB_LLM_DICTATION_VOSK_CONFIDENCE` (default 0, off) is the average word confidence required; lower it |
| Hands-free switched itself off | The microphone failed while listening; the reason is in zrb's log |
| Recording starts but no audio is captured | Check OS microphone permissions for your terminal app; on Linux, check that PulseAudio/PipeWire is running |
| Hands-free says "Error starting stream: Wait timed out" (PortAudio `paTimedOut`, `-9987`) | PortAudio never got the device in time — its ALSA thread has a one-second deadline, which WSLg's PulseAudio can miss under load or just after the VM wakes. Hands-free retries the open three times, and only then says why, naming the device it tried: point it at another with `ZRB_LLM_DICTATION_DEVICE` (`pulse` and `default` are not the same microphone; `python -c "import sounddevice; sounddevice.query_devices()"` lists them), and check the server is up (`pactl info`) |
| No sound on WSL | WSL2 needs WSLg (Windows 11) or a PulseAudio server bridged from Windows for audio passthrough |
| Termux: no microphone access | Dictation records through `sounddevice` (PortAudio), not Termux:API, so the microphone has to be reachable through PortAudio in your Termux environment; Termux:API is used only by `/photo` and the `termux` speech backend |

## Photo (`/photo`)

| Symptom | Solution |
|---------|----------|
| "Camera capture failed" with no other detail | Install `ffmpeg` — it's the capture backend on every desktop platform |
| macOS: capture fails or returns a black frame | Grant your terminal app camera access in **System Settings > Privacy & Security > Camera** — easy to miss, since the OS doesn't always prompt for a CLI tool |
| Linux: no camera found | Check `/dev/video0` exists and your user is in the `video` group (`sudo usermod -aG video $USER`, then re-login) |
| Windows: capture fails or picks the wrong camera | Auto-detection parses `ffmpeg -f dshow -list_devices true -i dummy`; if it fails or the machine has multiple cameras, run that command yourself to find the device name and pass it explicitly: `/photo "<device name>"` |
| WSL: no camera found / `/dev/video0` never appears, even after `usbipd attach` | `usbipd-win` alone is not enough — see [WSL2 camera passthrough](#wsl2-camera-passthrough-building-a-custom-kernel) below |
| WSL: capture hangs and the camera light stays on ("Camera capture failed" with a `capture timed out` detail) | `/dev/video0` exists, but usbipd-win's USB/IP tunnel can't sustain the video stream — see the note at the end of [WSL2 camera passthrough](#wsl2-camera-passthrough-building-a-custom-kernel) |
| WSL: `usbipd attach` fails with `Device busy (exported)` even after `usbipd bind` | Windows itself is still holding the camera. This is common for a laptop's **built-in/integrated camera** — Windows' Frame Server keeps a handle on it (for Windows Hello, the Camera app, background video-conferencing processes, etc.) and often won't release it even when nothing appears to be using it, sometimes not even after a reboot. An **external USB webcam** attaches far more reliably than an integrated one. If you must use the integrated camera, try closing Windows Hello/Camera/Teams/Zoom first, or as a last resort disable the built-in camera in Device Manager before attaching (`usbipd attach --wsl --busid=<id>`) — re-enable it afterward to use it on Windows again |
| Termux (native or `proot-distro`): "Camera capture failed" | Install the Termux:API app (F-Droid) and `pkg install termux-api`. `/photo` works from inside `proot-distro` too — the capture writes to Termux's real home directory rather than a temp path, so it's visible from both native Termux and a proot guest |

## WSL2 camera passthrough: building a custom kernel

[usbipd-win](https://github.com/dorssel/usbipd-win) only does USB-level passthrough — it gets the webcam enumerated on WSL2's USB bus (confirm with `lsusb` and `dmesg | tail`, which show the device even when nothing else works). Turning that into a `/dev/video0` node is the kernel's job, and the stock `microsoft-standard-WSL2` kernel ships with **no camera driver at all** — no `uvcvideo`, no v4l2 core, not even as a loadable module (`sudo modprobe uvcvideo` fails with `Module uvcvideo not found`). There is no config flag or package that fixes this; you have to build a custom kernel.

1. Match your exact running kernel version so the config is a known-good starting point:
   ```bash
   uname -r   # e.g. 5.15.153.1-microsoft-standard-WSL2
   ```
2. Install build tooling, then clone the matching tag from Microsoft's kernel repo (the tag `linux-msft-wsl-<version>` always exists for a version that's actually running):
   ```bash
   sudo apt-get install -y build-essential flex bison libelf-dev libncurses-dev libssl-dev bc dwarves git
   git clone --depth 1 -b linux-msft-wsl-5.15.153.1 \
     https://github.com/microsoft/WSL2-Linux-Kernel.git ~/wsl2-kernel-build/src
   ```
3. Base the config on the *currently running* kernel (guarantees every WSL2-specific option — hyperv, 9p, hv_sock — stays correct), then turn on USB Video Class support:
   ```bash
   cd ~/wsl2-kernel-build/src
   zcat /proc/config.gz > .config
   ./scripts/config --enable MEDIA_SUPPORT --enable MEDIA_CAMERA_SUPPORT \
     --enable MEDIA_USB_SUPPORT --enable MEDIA_SUPPORT_FILTER --enable VIDEO_DEV \
     --module USB_VIDEO_CLASS --enable USB_VIDEO_CLASS_INPUT_EVDEV
   make olddefconfig
   ```
4. Build and install:
   ```bash
   make -j$(nproc)
   sudo make modules_install -j$(nproc)
   sudo depmod -a && sync   # see the gotcha below — do this before anything else
   ```
5. Copy `vmlinux` to your Windows filesystem and point `.wslconfig` at it:
   ```bash
   cp vmlinux /mnt/c/Users/<you>/wsl2-uvc-vmlinux
   ```
   ```ini
   # C:\Users\<you>\.wslconfig -- this is machine-wide, applies to every WSL2 distro
   [wsl2]
   kernel=C:\Users\<you>\wsl2-uvc-vmlinux
   ```
6. From PowerShell: `wsl --shutdown`, then reopen WSL. Verify with `uname -r -v` (look for a trailing `+`), reattach the camera (`usbipd attach --wsl --busid=<id>`), and confirm `/dev/video0` exists.

**Gotcha:** `wsl --shutdown` force-powers-off the VM without flushing disk cache first — it is not a clean guest shutdown. If a `make modules_install` hasn't been `sync`ed to disk yet, ext4's journal replay silently rolls it back on the next boot, and `/dev/video0` goes missing again with `modprobe uvcvideo` failing as if the module was never built. Always run `sync` right after `modules_install`/`depmod`, before triggering any `wsl --shutdown`.

**Even after the driver works:** ffmpeg's default v4l2 negotiation requests raw YUYV at the camera's max resolution (often 1080p, ~165 Mbps uncompressed), which usbipd-win's USB/IP tunnel can't sustain — the capture hangs indefinitely with the camera light stuck on and no frame ever delivered. zrb works around this automatically by requesting MJPEG (compressed on-camera) at 640x480 first, falling back to the raw negotiation for cameras that don't support MJPEG; a 15-second capture timeout (`ZRB_LLM_CAMERA_TIMEOUT`) is the backstop if a given camera/setup hangs regardless. If `/photo` still times out at that point, try an external USB webcam — integrated ones are consistently less reliable over USB/IP.

---

🔖 [Documentation Home](../../README.md) > [LLM](./) > Voice & Photo Troubleshooting

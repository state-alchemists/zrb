🔖 [Documentation Home](../README.md) > [LLM](./) > Voice & Photo Troubleshooting

# Voice & Photo Troubleshooting

`/voice` and `/photo` depend on OS-level microphone/camera access, so failures are usually platform setup, not a zrb bug. Configuration knobs for both features are in [LLM Configuration → Voice and Camera](../configuration/llm-voice-camera.md#voice-and-camera); the commands themselves are listed under [TUI Commands](llm-integration.md#tui-commands).

---

## Table of Contents

- [Voice (`/voice`)](#voice-voice)
- [Photo (`/photo`)](#photo-photo)
- [WSL camera](#wsl-camera)
  - [Fallback: usbipd-win passthrough with a custom kernel](#fallback-usbipd-win-passthrough-with-a-custom-kernel)

---

## Voice (`/voice`)

| Symptom | Solution |
|---------|----------|
| `/voice` or `/handsfree` says dictation needs the `zrb[voice]` extra | `pip install 'zrb[voice]'` (sounddevice, numpy, vosk, pipecat-ai) |
| An error mentioning `vosk` | vosk is the default backend: install it, or switch `ZRB_LLM_DICTATION_BACKEND` to `openai`/`google`/`multimodal`, or to a local `whisper`/`moonshine`/`funasr` service |
| A message naming a speech service and the package it needs | The `zrb[voice]` extra brings Pipecat but none of its model packages, so a local service needs its own: `pip install 'pipecat-ai[whisper]'`, `[moonshine]`, `[funasr]`, `[kokoro]`, `[piper]` or `[pocket-tts]` — see [Voice and camera § Your own backend](voice-camera.md#your-own-backend) |
| `kokoro` will not install, on Python 3.14 | `kokoro-onnx` declares `requires_python <3.14`, so no release of it installs here. Name `piper` or `pocket` for speech instead |
| Hands-free never submits anything | Run `zrb voice mic-test` from `examples/voice-interaction`; if your speech stays under the threshold, lower `ZRB_LLM_DICTATION_THRESHOLD`. With wake words set, only utterances starting with one count |
| In a public place, the room's own conversation becomes turns | Set `ZRB_LLM_DICTATION_WAKE_WORDS`: nothing else tells a stranger's request from yours. `ZRB_LLM_DICTATION_NOISE_MARGIN` (raise it; `0` counts the room not at all) and `ZRB_LLM_DICTATION_MIN_WORDS` (2 or more) keep the room's background and a stray word out |
| Hands-free ignores what you say in a loud room | The bar is over the room: lower `ZRB_LLM_DICTATION_NOISE_MARGIN` (default 2; `0` disables it), lower `ZRB_LLM_DICTATION_MIN_WORDS`, or speak up |
| Hands-free goes quiet after a long sentence | The bar is measured from everything heard while zrb is silent, your own speech included, so a long uninterrupted sentence can sit above your next words until something about a quarter as loud as your voice — a breath or a sentence break — is heard. Lower `ZRB_LLM_DICTATION_NOISE_MARGIN`, or set it to `0` in a quiet room |
| zrb's speech stutters, and it talks on, while you talk over it | On speakers `ZRB_LLM_DICTATION_BARGE_IN_MARGIN` (3) is holding zrb's voice for what it hears of itself: the hold is given back a moment later, which is the price of not waiting for your words. Keep it at 3 and lower the playback volume, or use headphones |
| With wake words set, saying "stop" over zrb does nothing | Say the wake word first: only words starting with one count. After that, a stop word alone ("stop", "wait wait", "stop please") is exact and free; longer or odder wording ("please fucking stop", a stop in another language) goes to the small model when it is five words or fewer (`ZRB_LLM_DICTATION_INTERRUPT_JUDGE_MAX_WORDS`). `ZRB_LLM_DICTATION_INTERRUPT_JUDGE_ENABLED=off` leaves the word lists deciding alone |
| Saying "stop" over zrb sometimes cancels the turn and sometimes only silences its voice | A stop word alone (polite words, fillers and a repeat ignored) cancels the turn, as Esc does. Anything else short goes to the small model, which has 2 seconds (`ZRB_LLM_DICTATION_INTERRUPT_JUDGE_TIMEOUT`, raise it for a slow model); a request, a timeout or a failure only quiets the voice, and your words become a new message. Add the phrase to `ZRB_LLM_DICTATION_STOP_WORDS`, say the stop word alone, press Esc, or see [what zrb makes of the words](voice-camera.md#talking-over-zrb-barge-in) |
| What you say over zrb comes back with zrb's own words mixed in | The microphone hears zrb on speakers. On macOS, `ZRB_LLM_DICTATION_ENABLE_ECHO_CANCEL=on` (on under `ZRB_LLM_VOICE=conversation`) with `ZRB_LLM_DICTATION_DEVICE` empty; on Linux, load PulseAudio's or PipeWire's echo-cancel module and make its microphone and speakers the defaults; anywhere, headphones. See [Hearing zrb in what you say](voice-camera.md#hearing-zrb-in-what-you-say) |
| Saying "okay" or "got it" over zrb silences it but the agent never answers | That is the hush: zrb goes quiet and the work goes on, and the words are sent nowhere. Remove the phrase from `ZRB_LLM_DICTATION_HUSH_WORDS` if you want it taken as a message |
| Saying "no" over zrb no longer cancels the turn | "No" denies a tool approval, and is no longer a stop word. Add it to `ZRB_LLM_DICTATION_STOP_WORDS` for the old behavior |
| With the `vosk` backend, a sentence you said is dropped as too faint | `ZRB_LLM_DICTATION_VOSK_CONFIDENCE` (default 0, off) is the average word confidence required; lower it |
| Hands-free switched itself off | The microphone failed while listening; the reason is in zrb's log |
| Recording starts but no audio is captured | Check OS microphone permissions for your terminal app; on Linux, check that PulseAudio/PipeWire is running |
| Hands-free says "Error starting stream: Wait timed out" (PortAudio `paTimedOut`, `-9987`) | PortAudio never got the device in time — its ALSA thread has a one-second deadline, which WSLg's PulseAudio can miss under load or just after the VM wakes. Hands-free retries the open three times, and only then says why, naming the device it tried: point it at another with `ZRB_LLM_DICTATION_DEVICE` (`pulse` and `default` are not the same microphone; `python -c "import sounddevice; sounddevice.query_devices()"` lists them), and check the server is up (`pactl info`) |
| No sound on WSL | WSL2 needs WSLg (Windows 11) or a PulseAudio server bridged from Windows for audio passthrough |
| Termux: no microphone access | Dictation records through `sounddevice` (PortAudio), not Termux:API, so the microphone has to be reachable through PortAudio in your Termux environment; Termux:API is used only by `/photo` and the `termux` speech backend |

## Photo (`/photo`)

| Symptom | Solution |
|---------|----------|
| "Camera capture failed" with no other detail | Install `ffmpeg` — it's the capture backend on every desktop platform, and zrb does not install it: `brew install ffmpeg`, `sudo apt install ffmpeg`, or `winget install Gyan.FFmpeg` on Windows and WSL |
| macOS: capture fails or returns a black frame | Grant your terminal app camera access in **System Settings > Privacy & Security > Camera** — easy to miss, since the OS doesn't always prompt for a CLI tool |
| Linux: no camera found | Check `/dev/video0` exists and your user is in the `video` group (`sudo usermod -aG video $USER`, then re-login) |
| Windows: capture fails or picks the wrong camera | Auto-detection parses `ffmpeg -f dshow -list_devices true -i dummy`; if it fails or the machine has multiple cameras, run that command yourself to find the device name and pass it explicitly: `/photo "<device name>"` |
| WSL: "Camera capture failed" | Install ffmpeg **on Windows** (`winget install Gyan.FFmpeg`), then `wsl --shutdown` so `ffmpeg.exe` is on WSL's `PATH` — see [WSL camera](#wsl-camera) |
| WSL: `ffmpeg.exe` is installed on Windows, but zrb still reports it missing | WSL takes the Windows `PATH` from the terminal that starts it, and a terminal opened before the install still has the old one. Close every terminal, run `wsl --shutdown` from a new one, reopen WSL, and check `which ffmpeg.exe`. If it is still empty, symlink the shim into a directory already on your `PATH`: `ln -s /mnt/c/Users/<you>/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe ~/.local/bin/ffmpeg.exe` |
| WSL: `ffmpeg.exe` is installed but capture fails or picks the wrong camera | Run `ffmpeg.exe -f dshow -list_devices true -i dummy` and pass the name: `/photo "<device name>"` or `ZRB_LLM_CAMERA_DEVICE`. Check the camera works in a Windows app first |
| Windows or WSL: the camera is missing, and Device Manager shows a "USBIP Shared Device" in its place | An earlier `usbipd bind --force` is still in effect: it swaps Windows' camera driver for usbipd's, so Windows (and `ffmpeg.exe`) see no camera even after `usbipd detach`. `usbipd list` shows it as `Shared (forced)`. From an administrator PowerShell, run `usbipd unbind --busid <id>`, and the camera comes back |
| Windows or WSL: there is no camera to find | zrb captures only what Windows enumerates, so a listing with no `(video)` line means Windows has no camera attached right now — not a zrb problem. Open the Windows **Camera** app: if it finds none either, look in Device Manager. A camera shown greyed-out with **Code 45** ("not connected") has dropped off the bus, which a sleep/resume cycle can cause: *Action → Scan for hardware changes*, or a full reboot, brings it back. A camera privacy key (`Fn`), Windows' camera access settings, or a disabled **Integrated Camera** in BIOS/UEFI can also keep it away. A privacy switch does not: a camera switched off that way is still listed, and its photo is black (next row) |
| Windows or WSL: the photo is completely black, though the camera light comes on | The camera is blocked in hardware. *Settings → Bluetooth & devices → Cameras → <camera>* then says it "is blocked or turned off by a switch or button on your device", and video calls get no picture either. Look for a privacy slider over the lens, a camera key in the `F` row, or a slide switch on the laptop's side edge (common on Lenovo IdeaPad and Yoga), or turn off the camera privacy mode in the maker's app (Lenovo Vantage). Windows' camera access settings do not cause this: they block apps outright |
| Windows or WSL: capture fails with `Could not open encoder before EOF`, `Nothing was written into output file` or `Error during demuxing: I/O error` | The camera opened but sent no frames, because another app is using it: a video call, a browser tab with camera access, or the preview in *Settings → Cameras* ("An app is using the camera now"). Close it and run `/photo` again |
| WSL (usbipd fallback): `/dev/video0` never appears, even after `usbipd attach` | `usbipd-win` alone is not enough — see [the fallback](#fallback-usbipd-win-passthrough-with-a-custom-kernel) below |
| WSL (usbipd fallback): capture hangs and the camera light stays on (`capture timed out`) | `/dev/video0` exists, but usbipd-win's USB/IP tunnel can't sustain the video stream — see the note at the end of [the fallback](#fallback-usbipd-win-passthrough-with-a-custom-kernel) |
| WSL (usbipd fallback): `usbipd attach` fails with `Device busy (exported)` even after `usbipd bind` | Windows itself is still holding the camera. This is common for a laptop's **built-in/integrated camera** — Windows' Frame Server keeps a handle on it (for Windows Hello, the Camera app, background video-conferencing processes, etc.) and often won't release it even when nothing appears to be using it, sometimes not even after a reboot. Use Windows' `ffmpeg.exe` instead, which needs no attach. Otherwise, an **external USB webcam** attaches far more reliably; or close Windows Hello/Camera/Teams/Zoom first, or as a last resort disable the built-in camera in Device Manager before attaching — re-enable it afterward to use it on Windows again |
| Termux (native or `proot-distro`): "Camera capture failed" | Install the Termux:API app (F-Droid) and `pkg install termux-api`. `/photo` works from inside `proot-distro` too — the capture writes to Termux's real home directory rather than a temp path, so it's visible from both native Termux and a proot guest |

## WSL camera

On WSL, zrb takes the photo with Windows' own ffmpeg:

1. In Windows, install ffmpeg: `winget install Gyan.FFmpeg`.
2. Restart WSL so it picks up the new Windows `PATH`: close every terminal (one opened before the install still has the old `PATH`, and WSL takes it from there), run `wsl --shutdown` from a new PowerShell window, then reopen WSL. Check with `which ffmpeg.exe`. WSL adds the Windows `PATH` unless `appendWindowsPath=false` is set in `/etc/wsl.conf`.
3. `/photo`. zrb runs `ffmpeg.exe -f dshow` on the Windows side and auto-detects the first camera; `ffmpeg.exe -f dshow -list_devices true -i dummy` lists them, and `ZRB_LLM_CAMERA_DEVICE` picks one by name.

The camera is open only while the photo is taken, so Windows apps keep using it, and nothing is attached to WSL. A Windows app that holds the camera exclusively (some video-call apps do) can make a capture fail while it runs. A virtual camera, such as OBS's, lets several apps share one camera; name it in `ZRB_LLM_CAMERA_DEVICE` or `/photo "<name>"`, because auto-detection takes only the devices ffmpeg tags `(video)` and a virtual camera is listed without that tag, so it is never chosen for you.

zrb uses the Linux `ffmpeg` and `/dev/video0` instead when `ffmpeg.exe` is not on the `PATH`, or when the device is a `/dev/video*` path. That needs the fallback below.

### Fallback: usbipd-win passthrough with a custom kernel

This route takes the camera away from Windows while it is attached, and needs a kernel you build yourself. Prefer `ffmpeg.exe` above.

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

🔖 [Documentation Home](../README.md) > [LLM](./) > Voice & Photo Troubleshooting

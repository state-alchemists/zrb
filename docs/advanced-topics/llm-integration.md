🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a powerful, built-in AI assistant that can understand your codebase, perform actions on your behalf, and automate complex software engineering tasks.

This page covers the end-user surface: the interactive TUI, troubleshooting, and embedding `LLMTask`/`LLMChatTask` in your own project. To register custom tools, delegate to sub-agents, override model capabilities, or tune context management, see [Extending the LLM](extending-the-llm.md).

---

## Table of Contents

- [Interactive Chat](#interactive-chat-zrb-llm-chat)
  - [TUI Commands](#tui-commands)
  - [Session Token Tracking](#session-token-tracking)
  - [Approval Policies](#approval-policies)
  - [Troubleshooting: Voice & Photo](#troubleshooting-voice--photo)
- [Permission Policy System](./permission-policy.md)
- [Sandbox (Filesystem Containment)](./sandbox.md)
- [Plan Mode](./plan-mode.md)
- [Programmatic Usage](#programmatic-usage-llmtask-and-llmchattask)
- [Quick Reference](#quick-reference)
- [Extending the LLM](extending-the-llm.md) — built-in tools, custom tools, sub-agents, model capabilities, context management

---

## Interactive Chat (`zrb llm chat`)

The primary way to interact with AI Assistant is through an interactive terminal user interface (TUI).

```bash
zrb llm chat "Can you help me refactor the user authentication service?"
```

This launches a full-screen chat application where you can have a conversation with the assistant.

### TUI Commands

| Command | Description |
|---------|-------------|
| `/q`, `/bye`, `/quit`, `/exit` | Exit the application |
| `/info`, `/help` | Show all available commands |
| `/compress`, `/compact` | Summarize conversation to free context |
| `/model <name>` | Switch LLM model (e.g., `/model openai:gpt-4o`) |
| `/yolo` or `/yolo <tools>` | Toggle auto-execute mode. With tool names (e.g., `/yolo Write,Edit`), selectively auto-approve only those tools |
| `/load <name>` | Load a named session |
| `/save <name>` | Save current session |
| `/attach <file_path>` | Attach a file to next message (capped by `LLM_MAX_ATTACHMENT_BYTES`, default 20MB; content is sniffed against its extension) |
| `/photo [device]` | Capture a photo from the camera and attach it to the next message (device is optional; auto-detected per platform) |
| `>` or `/redirect` (bare) | Copy last AI response to clipboard |
| `>` or `/redirect <file_path>` | Save last AI response to a file |
| `/copy` (bare) | Copy full conversation transcript to clipboard |
| `/copy <file_path>` | Save full conversation transcript to file |
| `!` or `/exec <shell_cmd>` | Execute shell command |
| `/btw <text>` | Inject a side note for the next turn without sending it as a message (runs while the assistant is thinking) |
| `/plan` | Toggle [Plan Mode](./plan-mode.md) (read-only discovery) |
| `/rewind [n\|sha]` | List or restore filesystem + history [snapshots](../configuration/llm-config.md#6-rewind--snapshots) (requires `ZRB_LLM_ENABLE_REWIND`) |
| `/voice` | Toggle push-to-talk voice dictation on/off (requires `ZRB_LLM_VOICE_ENABLED`; see [Voice Dictation](../configuration/llm-config.md#23-voice-dictation)) |

> 💡 **Tip:** Any `/command` that matches a loaded skill will be executed as a skill.
>
> The token(s) that trigger each command are configurable — see [Slash Command Aliases](../configuration/llm-config.md#17-slash-command-aliases).

### Session Token Tracking

The TUI status bar tracks accumulated LLM token usage across all requests in a session. After the first LLM request completes, the status bar displays a token count like:

```
💸 1.5k in · 34 out
```

The counters reset whenever you switch conversations via `/load`, since past sessions' spend is not persisted. Tokens are tracked per-UI instance — in a `MultiUI` setup each child UI maintains its own totals.

There are no configuration knobs for this feature; it always appears (non-zero after the first request) and uses the theme's `FAINT` style.

### Approval Policies

By default, Zrb prompts for confirmation before executing most tools. This is controlled by YOLO mode and the [Permission Policy](./permission-policy.md) system:

| Mode | Behavior |
|------|----------|
| **YOLO off** | All tools require confirmation |
| **YOLO on** | All tools auto-approved |
| **Selective YOLO** | Only specified tools auto-approved (e.g., `/yolo Write,Edit`) |
| **Permission Policy** | Fine-grained `ALLOW`/`DENY`/`ASK` rules that can override YOLO |
| **Plan Mode** | Strict read-only mode for discovery. See [Plan Mode](./plan-mode.md) |

**Safe Command Policy:** The `Shell` tool automatically approves known-safe read-only commands (e.g., `ls`, `git status`, `cat`, `grep`) without requiring YOLO mode. Commands with dangerous shell metacharacters (`>`, `|`, `;`, `&`, `` ` ``, `$()`, `\n`, `\r`) always require explicit approval. Known-safe prefixes include `ls`, `cat`, `grep`, `git status`, `printenv`, and similar read-only commands — note that bare `env` is intentionally excluded as `env FOO=1 rm -rf x` can execute arbitrary commands.

### Troubleshooting: Voice & Photo

`/voice` and `/photo` depend on OS-level microphone/camera access, so failures are usually platform setup, not a zrb bug.

**Voice (`/voice`):**

| Symptom | Solution |
|---------|----------|
| `/voice` says voice dictation is disabled | Set `ZRB_LLM_VOICE_ENABLED=true` — see [Voice Dictation](../configuration/llm-config.md#23-voice-dictation) |
| `RuntimeError` mentioning `sounddevice` or `vosk` | Those are optional dependencies: `pip install sounddevice vosk numpy` (or switch `ZRB_LLM_VOICE_MODE` to `openai`/`google`/`multimodal`) |
| Recording starts but no audio is captured | Check OS microphone permissions for your terminal app; on Linux, check that PulseAudio/PipeWire is running |
| No sound on WSL | WSL2 needs WSLg (Windows 11) or a PulseAudio server bridged from Windows for audio passthrough |
| Termux: no microphone access | Install `termux-api` (`pkg install termux-api`) and the Termux:API app from F-Droid; grant microphone permission to Termux:API in Android settings |

**Photo (`/photo`):**

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

#### WSL2 camera passthrough: building a custom kernel

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

**Even after the driver works:** ffmpeg's default v4l2 negotiation requests raw YUYV at the camera's max resolution (often 1080p, ~165 Mbps uncompressed), which usbipd-win's USB/IP tunnel can't sustain — the capture hangs indefinitely with the camera light stuck on and no frame ever delivered. zrb works around this automatically by requesting MJPEG (compressed on-camera) at 640x480 first, falling back to the raw negotiation for cameras that don't support MJPEG; a 15-second capture timeout is the backstop if a given camera/setup hangs regardless. If `/photo` still times out at that point, try an external USB webcam — integrated ones are consistently less reliable over USB/IP.

---

## Programmatic Usage (`LLMTask` and `LLMChatTask`)

You can also integrate the LLM directly into your automated workflows using two specialized task types. Both accept `message`, `system_prompt`, and `prompt_manager` as values, templates, callables, or sections — see the full guide at **[Programming the Prompt](programming-the-prompt.md)** for examples of each rung.

### `LLMTask` (Single-Shot)

Use `LLMTask` for single-shot requests where you need the LLM to process input and return a result without conversational history.

```python
from zrb import LLMTask, cli

summarize_task = cli.add_task(
    LLMTask(
        name="summarize",
        system_prompt="You are an expert summarizer.",
        message="Please summarize the following text: {ctx.input.text}"
    )
)
```

### `LLMChatTask` (Conversational)

Use `LLMChatTask` to create your own fully customizable, interactive chat interfaces.

```python
from zrb import LLMChatTask, cli, StrInput

custom_chat = cli.add_task(
    LLMChatTask(
        name="custom-chat",
        ui_greeting="Hello from your custom assistant!",
        input=[StrInput(name="user_message", ...)],
        message="{ctx.input.user_message}"
    )
)
```

> 📖 **API Reference:** For the full `LLMChatTask` builder API — tools, guidance, hooks, policies, triggers, and custom commands — see the [LLMChatTask API Reference](../task-types/llmchat-task.md).

### Comparison

| Feature | `LLMTask` | `LLMChatTask` |
|---------|-----------|---------------|
| **Use case** | Single-shot processing | Interactive chat |
| **History** | None | Persistent session |
| **TUI** | No | Yes |
| **Custom tools** | Yes | Yes |

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `zrb llm chat` | Start interactive chat |
| `zrb llm chat "message"` | Start with initial message |

| Task Type | Import | Use Case |
|-----------|--------|----------|
| `LLMTask` | `from zrb import LLMTask` | Single processing |
| `LLMChatTask` | `from zrb import LLMChatTask` | Interactive chat |

---

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration

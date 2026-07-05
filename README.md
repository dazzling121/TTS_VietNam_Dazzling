# TTS Studio Unified

Unified local UI for Kokoro Vietnamese and VieNeu-TTS, styled as a TTS Studio workflow.

## Layout

- `app.py`: Gradio controller UI.
- `services/task_queue.py`: in-memory task queue.
- `services/subtitle_io.py`: SRT/VTT import and script cleaning.
- `services/text_cleaner.py`: Vietnamese TTS text cleaning and normalization.
- `services/export_io.py`: TXT/SRT/VTT export helpers.
- `services/gpu_status.py`: NVIDIA GPU status helper.
- `workers/kokoro_worker.py`: JSON-lines worker. The app uses an existing Kokoro venv if present, otherwise it creates `runtimes\kokoro\.venv`.
- `workers/vieneu_worker.py`: JSON-lines worker. The app uses an existing VieNeu venv if present, otherwise it creates `runtimes\vieneu\.venv`.
- `voices/user_clones/`: user clone voice profiles.
- `outputs/`: generated WAV files.
- `logs/`: worker stderr and raw stdout logs.

## Run

For a new machine, start here.

Windows:

```text
START_HERE.bat
```

macOS/Linux:

```bash
chmod +x START_HERE.sh install_unix.sh run_unified.sh
./START_HERE.sh
```

To only check what is missing on Windows:

```powershell
.\START_HERE.bat -CheckOnly
```

To only check what is missing on macOS/Linux:

```bash
./START_HERE.sh --check-only
```

The beginner installer detects the operating system. Windows uses the PowerShell installer; macOS/Linux use the shell installer with Homebrew or the detected Linux package manager. See `SETUP_CHO_NGUOI_MOI.md`.

```powershell
cd <folder-you-extracted-or-cloned-TTS-Unified>
.\.venv\Scripts\Activate.ps1
python app.py --server-name 127.0.0.1 --server-port 7870
```

Or:

```powershell
.\run_unified.ps1
```

macOS/Linux:

```bash
./run_unified.sh
```

## Stop Safely

Windows:

```text
STOP_HERE.bat
```

macOS/Linux:

```bash
chmod +x STOP_HERE.sh stop_tool_unix.sh
./STOP_HERE.sh
```

Open:

```text
http://127.0.0.1:7870
```

## Notes

- Only one worker is active at a time.
- Switching engine unloads the previous worker.
- Task generation can target GPU, CPU, or Auto device selection from the UI.
- The main Create Voice page now generates audio directly from the text input without requiring queue steps.
- Kokoro can use a pre-existing runtime, or the app can bootstrap `runtimes\kokoro\.venv` from the Kokoro Vietnamese GitHub source package.
- VieNeu can use a pre-existing runtime, or the app can bootstrap `runtimes\vieneu\.venv` with the official `vieneu` package.
- The two source projects are not modified by this unified UI.
- Pitch is currently captured in task settings for UI parity, but the underlying engines do not expose a native pitch parameter yet.
- VieNeu clone profiles use a user reference audio file. Kokoro clone profiles are saved as local aliases/presets over its installed voicepacks.

## Verified

Checked on 2026-07-05:

- `list_voices` works for Kokoro and VieNeu.
- Task queue can add manual tasks.
- SRT import creates multiple tasks.
- Kokoro queue generation works through the app and through the Gradio server API.
- VieNeu queue generation works through the app.
- TXT/SRT/VTT export helpers work.
- Worker unload returns the app to no active TTS worker.
- The Gradio server is running at `http://127.0.0.1:7870`.

Implementation checklist:

- [x] TTS Studio 3-column layout.
- [x] Clickable sidebar navigation.
- [x] Overview page with local CPU/RAM/GPU scan and model/device recommendation.
- [x] Simple direct Create Voice page.
- [x] Vietnamese TTS cleaner for Unicode, subtitle noise, dates, times, numbers, currency, percentages, units, URLs, email, and common abbreviations.
- [x] Content editor with optional cleaned text preview.
- [x] Backend task queue preserved for older/API batch workflows.
- [x] Direct generate, listen, open file, and regenerate actions.
- [x] Right-side engine, voice, preset, speed, pitch, volume, emotion, temperature controls.
- [x] GPU/CPU/Auto device selector for generation.
- [x] Clone Voice page with preview generation and saved user clone profiles.
- [x] Voice Library page for Kokoro, VieNeu, and user clones.
- [x] TXT/SRT/VTT output options and filename template.
- [x] GPU badge/status panel.
- [x] Kokoro and VieNeu JSON-lines workers preserved.
- [x] Single-active-worker GPU policy preserved.

To stop the running app, find the owner of port `7870`:

```powershell
Get-NetTCPConnection -LocalPort 7870
```

Then stop that process id:

```powershell
Stop-Process -Id <PID>
```

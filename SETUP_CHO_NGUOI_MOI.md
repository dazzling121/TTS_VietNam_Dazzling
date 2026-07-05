# TTS Studio - Cai Dat Cho Nguoi Moi

Muc tieu: may moi chua co Python van co duong cai dat theo he dieu hanh.

## Chay file nao?

Windows:

```text
START_HERE.bat
```

macOS/Linux:

```bash
chmod +x START_HERE.sh install_unix.sh run_unified.sh
./START_HERE.sh
```

Chi kiem tra thieu gi:

```powershell
.\START_HERE.bat -CheckOnly
```

```bash
./START_HERE.sh --check-only
```

## Tool tu nhan dien OS nhu the nao?

- Windows: `START_HERE.bat` goi `install_fresh_windows.ps1`.
- macOS/Linux: `START_HERE.sh` doc `uname -s`.
- macOS se dung Homebrew.
- Linux se tu chon package manager neu co: `apt`, `dnf`, `pacman`, `zypper`, hoac `apk`.

## Script se cai nhung gi?

Windows:

1. Python 3.12 x64 neu thieu.
2. Microsoft Visual C++ Redistributable x64.
3. FFmpeg local vao `tools\ffmpeg`.
4. App venv `.venv`.
5. Model runtimes trong `runtimes\`.
6. Mo web app tai `http://127.0.0.1:7870`.

macOS:

1. Homebrew neu thieu.
2. `python@3.12`, `git`, `ffmpeg`.
3. App venv `.venv`.
4. Model runtimes trong `runtimes/`.
5. Mo web app tai `http://127.0.0.1:7870`.

Linux:

1. Python 3, pip, venv, git, curl, unzip, build tools.
2. FFmpeg neu package manager ho tro.
3. App venv `.venv`.
4. Model runtimes trong `runtimes/`.
5. Mo web app tai `http://127.0.0.1:7870`.

## Thu muc model mac dinh

Windows:

```text
%USERPROFILE%\TTS\Models
```

macOS/Linux:

```text
~/TTS/Models
```

Co the doi bang tham so:

```powershell
.\START_HERE.bat -ModelRoot "D:\TTS\Models"
```

```bash
./START_HERE.sh --model-root "$HOME/TTS/Models"
```

## GPU

Script khong tu cai driver GPU vi driver phu thuoc phan cung va co the can khoi dong lai.

Windows/Linux NVIDIA:

```bash
nvidia-smi
```

Neu len thong tin GPU/driver thi co the cai them PyTorch CUDA:

```powershell
.\START_HERE.bat -InstallGpuTorch
```

```bash
./START_HERE.sh --install-gpu-torch
```

macOS Apple Silicon dung PyTorch macOS/macOS MPS qua wheel macOS mac dinh.

## Log

```text
logs/install-latest.log
logs/stop-latest.log
logs/runtime_bootstrap.log
tts_server_7870.err.log
logs/vieneu_worker.err.log
logs/kokoro_worker.err.log
```

## Tat tool an toan

Windows:

```text
STOP_HERE.bat
```

macOS/Linux:

```bash
./STOP_HERE.sh
```

Script se dung worker model truoc, sau do dung web app. No chi dung process co command line nam trong thu muc du an.

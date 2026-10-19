# Punch & Roll Studio

A small local web interface for [PunchAndRollAutomation](https://github.com/daveshap/PunchAndRollAutomation) (the `punchroll` audiobook-editing toolkit). Instead of typing commands and file paths, you pick a step from a sidebar, browse for your files with the normal Windows / macOS / Linux file dialog, press **Run**, and watch the output live.

> **Unofficial.** This is an independent companion project. It is not affiliated with or endorsed by the author of PunchAndRollAutomation. It does not contain or redistribute any of that project's code: it installs it from the upstream repository and calls it as `python -m punchroll ...`.

<!-- Add a screenshot here: docs/screenshot.png -->

## Features

- **One form per command.** Every `punchroll` command (transcribe, cut, readback, clicks, lost, markcheck, declick, standards, verify, batch, scorecard, said, assemble, picture) has its options laid out as fields, with a live preview of the exact command line.
- **Native file pickers.** A **Browse…** button on every file, output and folder field opens your operating system's own dialog. No more typing paths.
- **Mark-up editor.** Load a `markup/*.md` file, edit it, save it, and run `markcheck` on it in one click (Ctrl+S saves).
- **Live console.** Output streams as the command runs, with a Stop button.
- **One-click setup.** Downloads the upstream repo if you don't have it, installs it with all extras (CUDA PyTorch first if an NVIDIA GPU is found), and fetches the speech models.
- **Switch projects** without restarting, using *Change folder…* in the sidebar.
- **Zero dependencies.** The UI itself uses only the Python standard library.

## Quick start

### Windows

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/) (tick *Add python.exe to PATH*). The upstream project uses 3.13.
2. Put `punchroll_ui.py` and `start_punchroll_ui.bat` in your audiobook project folder (the one that holds, or will hold, `raw/`, `markup/` and `edited/`).
3. Double-click **`start_punchroll_ui.bat`**.

The first run installs everything, which can take a while (a CUDA PyTorch download alone is a few GB). Later runs start in seconds. Your browser opens at <http://127.0.0.1:8765>.

### macOS / Linux

```bash
cd /path/to/your/audiobook-project
python3 punchroll_ui.py --auto-setup
```

On Debian/Ubuntu you may need `sudo apt install python3-tk` for the file dialog (see [Troubleshooting](#troubleshooting)).

### Command-line options

| Option | Meaning |
| --- | --- |
| `--root FOLDER` | Project folder to work in (default: current folder). |
| `--port N` | Port to listen on (default 8765). |
| `--auto-setup` | Install punchroll first, but only if it is missing. |
| `--setup` | Run install/repair now, then start the UI. |
| `--repo FOLDER` | Use an existing PunchAndRollAutomation checkout instead of downloading one. |
| `--no-cuda` | Skip the GPU build of PyTorch. |
| `--no-models` | Skip the speech-model download. |
| `--no-browser` | Don't open a browser window. |

## How the workflow maps to the UI

| Step | Where in the UI |
| --- | --- |
| Install, download models | **Setup → Install / repair** |
| 1. Transcribe a recording | **Edit → Transcribe** |
| 2. Read the transcript and write the mark-up | Done by Claude Code (see below). Review or tweak it in **Mark-up editor**. |
| 3. Render and master | **Edit → Render & master** |
| 4. Check the result | **Check →** Readback, Clicks, Lost material, Mark-up check, Declick, Standards, Verify, Spectrogram |
| Whole books | **Project →** Batch, Scorecard, Assemble pickups, What was said |

**What this UI does not do:** the upstream workflow has Claude Code read the whole transcript and decide what to keep, cut and retime. This interface does not call an AI model. It runs the tooling around that step and lets you inspect and adjust the result. See the upstream README and docs for how that step works.

## How it works

`punchroll_ui.py` starts a tiny HTTP server on `127.0.0.1` and serves a single-page interface. Each **Run** starts `python -m punchroll <command> ...` as a subprocess in your project folder and streams its output to the page. File dialogs are opened by the server through `tkinter` (or `osascript` / `zenity` / `kdialog` as fallbacks) because browsers don't reveal full file paths.

Safety notes:

- The server only listens on localhost and rejects requests with an unexpected `Host` header.
- Only the listed `punchroll` commands (plus the installer) can be run.
- The mark-up editor can only read and write inside the current project folder.
- The local server has no login or password (it is only reachable from your own computer). Don't expose the port to a network. This is unrelated to AI accounts or API keys, which the UI never uses.

## What runs where

| Part | What it is | Where it runs |
| --- | --- | --- |
| **Punch & Roll Studio** (this repo) | A standard-library Python server plus one web page. It builds command lines, starts them, shows their output, opens file dialogs and edits mark-up text files. It does no audio processing and contains no AI. | Your computer |
| **The engine: [PunchAndRollAutomation](https://github.com/daveshap/PunchAndRollAutomation#readme)** (`punchroll`) | Does the real work: transcription, editing, mastering and quality analysis. According to its README, speech models are downloaded once and cached, and the heaviest number-crunching can use an NVIDIA GPU through PyTorch. See its [README](https://github.com/daveshap/PunchAndRollAutomation#readme) and [docs](https://github.com/daveshap/PunchAndRollAutomation/tree/main/docs) for exactly what each command does. | Your computer, installed by this tool's setup |
| **Claude Code** | In the upstream workflow, Claude reads the transcript and decides what to keep, cut and retime. | Not part of this UI; you run it separately if you want that step |

**Accounts, tokens and cost.** This UI never calls an AI service, needs no API key and uses no tokens. Using it costs nothing beyond your own computer's time and disk space. Any Claude usage happens separately, in Claude Code, under whatever plan you use there.

**Network use.** Only during setup: GitHub (the upstream code), PyPI (Python packages), download.pytorch.org (GPU PyTorch) and wherever `punchroll models` fetches its speech models. The UI itself makes no outbound requests, and your audio is never uploaded by it. Whether the engine contacts anything else is determined by the upstream code; if that matters to you, read its source or run it with the network disconnected after setup.

**This project depends on the engine.** It is independent code, but it does nothing useful without `punchroll` installed.

## Keeping it working

This is a thin wrapper around a fast-moving project, so it needs occasional maintenance:

- **Command options are hard-coded.** The forms mirror the upstream command-line options as documented at the time of writing. If upstream renames or adds options, a form may fail or miss a feature. `python -m punchroll <command> --help` is the source of truth.
- **Setup follows upstream's `main` branch** and its extras `.[all,pictures,listen]`. A new upstream commit, a renamed extra, or an unsupported new Python version can break a fresh install. Setup does not update an existing copy: to update, run `git pull` inside the `PunchAndRollAutomation` folder (or delete the folder and run **Install / repair** again).
- **GPU PyTorch uses a fixed index URL** (`cu126`). If that build is retired, setup falls back to CPU PyTorch.

Tested against upstream commit: _fill in before release_.

## Troubleshooting

**Red banner: "punchroll is not installed in …"**
The Python that started the UI doesn't have punchroll. Open **Install / repair** and press Run, or start with `--setup`. If you have several Pythons, always launch the UI with the one you installed into. (The `.bat` prefers `py -3.13`.)

**Browse… does nothing or shows "No file dialog available"**
Install tkinter: `sudo apt install python3-tk` (Debian/Ubuntu), `sudo dnf install python3-tkinter` (Fedora), or reinstall Python from python.org on Windows/macOS. You can always type a path instead.

**The file dialog is hidden**
It sometimes opens behind the browser. Check your taskbar or Dock.

**CUDA PyTorch install fails**
Setup falls back to the CPU build automatically. Re-run with the GPU build later using the command in the upstream README, or set `PUNCHROLL_DEVICE=cpu` to keep everything on the CPU.

**A command fails with an unknown option**
The upstream tool changes quickly and this UI mirrors its command-line options at the time of writing. Compare the form with `python -m punchroll <command> --help`, and please open an issue.

## Status and limitations

Early and lightly tested. Command forms were written from the upstream README, and not every command has been exercised end to end. Reports and spectrograms are written to files by punchroll and are not previewed in the UI yet.

Ideas for later: in-app report and spectrogram viewer, waveform preview, a `settings.toml` editor, multi-file selection.

## Repository layout

```
punchroll_ui.py            the whole app (server + interface + setup)
start_punchroll_ui.bat     Windows one-click launcher
README.md
LICENSE
```

## Contributing

Issues and pull requests are welcome. Please keep the UI dependency-free (standard library only) and keep it a thin layer over the `punchroll` CLI, so that upstream changes are easy to follow.

## License

MIT for the code in this repository (see `LICENSE`). PunchAndRollAutomation is a separate project with its own terms; check its repository before redistributing it.

## Credits

Built around [daveshap/PunchAndRollAutomation](https://github.com/daveshap/PunchAndRollAutomation). All the actual audio processing is done by that project.

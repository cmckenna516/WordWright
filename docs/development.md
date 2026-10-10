# Running from source, tests, and troubleshooting

Installed users don't need anything here. These steps are for contributors and
for testing straight from the repository.

## Run from the source folder

1. Download the repository ZIP, right-click it, and choose **Extract All**.
   Don't run setup from inside the ZIP.
2. In the extracted folder, double-click **Setup Wordwright.cmd** and allow it
   to run if Windows asks.
3. Keep the window open while it installs dependencies and downloads the speech
   model chosen for this PC. This takes several minutes and needs an internet
   connection.
4. Setup briefly opens the default microphone and checks speech recognition,
   the clipboard fallback, and the global hotkey hook. It keeps none of the
   audio or the test transcript.
5. When it says **Wordwright setup and functional checks are complete**,
   double-click **Start Wordwright.cmd**.

Setup looks for an existing Python 3.11 or 3.12. If it can't find one, install
Python and select **Add Python to PATH**, then run setup again.

## If the app doesn't appear

1. Run **Setup Wordwright.cmd** again and wait for the completion message. Any
   other ending means setup failed; the last check shown names the failing
   part.
2. Run **Start Wordwright.cmd** again. It stays open with an error if
   Wordwright exits immediately.
3. Logs are in `%LOCALAPPDATA%\Wordwright\logs\wordwright.log`. They include
   the detected hardware and chosen model, but never transcript text.

## Developer setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Useful commands:

```powershell
# List microphone inputs
.\.venv\Scripts\python.exe -m wordwright --list-microphones

# Run with diagnostic logging
.\scripts\run-debug.ps1

# Run without a console window
.\scripts\run.ps1

# Force a specific model, bypassing the Settings choice
.\.venv\Scripts\python.exe -m wordwright --model small.en --device cpu

# Time a model on this PC with a 16-bit WAV file
.\.venv\Scripts\python.exe scripts\smoke_model.py --model-dir .models --model base.en --audio sample.wav
```

Settings live in `%LOCALAPPDATA%\Wordwright\settings.json` and models in
`%LOCALAPPDATA%\Wordwright\models`.

## GPU acceleration

`large-v3-turbo` on an NVIDIA GPU is the most accurate option and is also fast.
faster-whisper needs cuBLAS for CUDA 12 and cuDNN 9 on the `PATH`; the NVIDIA
driver alone isn't enough. Wordwright checks for `cublas64_12.dll` and
`cudnn_ops64_9.dll` before choosing the GPU and falls back to the CPU if
loading the GPU model fails.

## Automated tests

GitHub Actions runs the unit tests and builds the packaged app for every pull
request into `main`. To run the tests locally:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Use the [dictation accuracy test script](test-script.md) to compare models and
releases by ear.

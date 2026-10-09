# Third-party notices

Wordwright's own code is released under the [MIT License](LICENSE). It depends
on the open-source projects below. The packaged Windows installer bundles these
libraries; running from source installs them from PyPI. Each project remains
under its own license, and its copyright belongs to its authors.

## Speech model

| Component | License | Notes |
| --- | --- | --- |
| Whisper `small.en` model weights (OpenAI), CTranslate2 conversion `Systran/faster-whisper-small.en` | MIT | Downloaded from Hugging Face on first launch; not stored in this repository |

## Direct dependencies

| Package | License | Project |
| --- | --- | --- |
| faster-whisper | MIT | https://github.com/SYSTRAN/faster-whisper |
| CTranslate2 | MIT | https://github.com/OpenNMT/CTranslate2 |
| PyAV (`av`) | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| FFmpeg libraries bundled in PyAV wheels | LGPL-3.0-or-later (as reported by the bundled build); bundled codec libraries carry their own licenses | https://ffmpeg.org |
| NumPy | BSD-3-Clause | https://numpy.org |
| Pillow | MIT-CMU (HPND) | https://python-pillow.org |
| pynput | LGPL-3.0 | https://github.com/moses-palmer/pynput |
| pyperclip | BSD-3-Clause | https://github.com/asweigart/pyperclip |
| pystray | LGPL-3.0 | https://github.com/moses-palmer/pystray |
| sounddevice | MIT | https://github.com/spatialaudio/python-sounddevice |

## Notable transitive dependencies

| Package | License |
| --- | --- |
| onnxruntime | MIT |
| huggingface_hub, tokenizers, hf-xet | Apache-2.0 |
| tqdm | MPL-2.0 and MIT |
| certifi | MPL-2.0 |

Run `python -m pip show <package>` in a Wordwright environment for exact
versions and license metadata.

## LGPL components

pynput, pystray, and the FFmpeg libraries are licensed under the GNU Lesser
General Public License. Wordwright uses them unmodified. Their complete source
code is available from the project links above. In the packaged application
they remain separate Python modules and shared libraries inside the install
folder, and you may replace them with compatible versions you build yourself.

## Packaging tools

The Windows build uses PyInstaller (GPL-2.0 with an exception that permits
distributing bundled applications under any license) and Inno Setup (Inno Setup
License). Neither changes the license of Wordwright or its dependencies.

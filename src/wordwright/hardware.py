"""Pick a speech model that suits the machine Wordwright is running on."""

from __future__ import annotations

import ctypes
import logging
import os
import platform
from ctypes import wintypes
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

AUTO = "auto"
MODEL_LABELS: dict[str, str] = {
    AUTO: "Automatic (recommended)",
    "large-v3-turbo": "Large v3 Turbo · most accurate, needs NVIDIA GPU",
    "small.en": "Small (English) · balanced",
    "base.en": "Base (English) · fastest",
}
MODEL_CHOICES = tuple(MODEL_LABELS)

# GPU inference in faster-whisper needs cuBLAS for CUDA 12 and cuDNN 9. The
# NVIDIA driver alone is not enough, and a missing cuDNN can abort the process
# on first use instead of raising, so check that these load before choosing CUDA.
_CUDA_RUNTIME_DLLS = ("cublas64_12.dll", "cudnn_ops64_9.dll")
_IMAGE_FILE_MACHINE_ARM64 = 0xAA64


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    native_arm64: bool
    logical_cpus: int
    memory_gb: float | None
    cuda_ready: bool

    @property
    def cpu_threads(self) -> int:
        """Threads for CPU transcription.

        faster-whisper uses 4 by default, which leaves most of a modern CPU
        idle. Half the logical CPUs, capped at 8, finishes sooner while leaving
        the rest of the machine responsive during a transcription burst.
        """

        return max(4, min(8, self.logical_cpus // 2))

    def describe(self) -> str:
        memory = f"{self.memory_gb:.0f} GB RAM" if self.memory_gb else "unknown RAM"
        arch = "ARM64" if self.native_arm64 else "x64"
        gpu = "usable NVIDIA GPU" if self.cuda_ready else "no usable GPU"
        return f"{arch}, {self.logical_cpus} logical CPUs, {memory}, {gpu}"


@dataclass(frozen=True, slots=True)
class ModelPlan:
    model: str
    device: str
    compute_type: str
    reason: str
    fallback: ModelPlan | None = None

    @property
    def label(self) -> str:
        return f"{self.model} · {'GPU' if self.device == 'cuda' else 'CPU'}"


def cpu_plan(profile: HardwareProfile) -> ModelPlan:
    if profile.native_arm64:
        # CTranslate2 publishes no Windows ARM64 build, so on ARM PCs the speech
        # engine runs under x64 emulation and the smaller model stays responsive.
        return ModelPlan(
            "base.en", "cpu", "int8",
            "ARM64 PC: the speech engine runs under x64 emulation",
        )
    memory_ok = profile.memory_gb is None or profile.memory_gb >= 12
    if profile.logical_cpus >= 8 and memory_ok:
        return ModelPlan("small.en", "cpu", "int8", "Capable CPU, no usable NVIDIA GPU")
    return ModelPlan("base.en", "cpu", "int8", "Lighter CPU: favoring speed")


def recommend(profile: HardwareProfile) -> ModelPlan:
    if profile.cuda_ready:
        return ModelPlan(
            "large-v3-turbo", "cuda", "float16",
            "NVIDIA GPU with CUDA libraries detected",
            fallback=cpu_plan(profile),
        )
    return cpu_plan(profile)


def resolve(choice: str, profile: HardwareProfile) -> ModelPlan:
    """Turn the Settings choice into a concrete model, device, and precision."""

    if choice == AUTO or choice not in MODEL_LABELS:
        return recommend(profile)
    cpu = ModelPlan(choice, "cpu", "int8", "Chosen in Settings")
    if profile.cuda_ready:
        return ModelPlan(choice, "cuda", "float16", "Chosen in Settings", fallback=cpu)
    return cpu


def detect_hardware() -> HardwareProfile:
    profile = HardwareProfile(
        native_arm64=_native_arm64(),
        logical_cpus=os.cpu_count() or 1,
        memory_gb=_memory_gb(),
        cuda_ready=_cuda_ready(),
    )
    LOGGER.info("Hardware: %s", profile.describe())
    return profile


def _native_arm64() -> bool:
    """True on ARM64 hardware, even when this x64 process runs under emulation."""

    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_current_process = kernel32.GetCurrentProcess
            get_current_process.restype = wintypes.HANDLE
            is_wow64_process2 = kernel32.IsWow64Process2
            is_wow64_process2.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.USHORT),
                ctypes.POINTER(wintypes.USHORT),
            ]
            is_wow64_process2.restype = wintypes.BOOL
            process_machine = wintypes.USHORT()
            native_machine = wintypes.USHORT()
            if is_wow64_process2(
                get_current_process(),
                ctypes.byref(process_machine),
                ctypes.byref(native_machine),
            ):
                return native_machine.value == _IMAGE_FILE_MACHINE_ARM64
        except (AttributeError, OSError):
            pass
    return platform.machine().lower() in {"arm64", "aarch64"}


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _memory_gb() -> float | None:
    try:
        if os.name == "nt":
            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullTotalPhys / 1024**3
            return None
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (AttributeError, OSError, ValueError):
        return None


def _cuda_ready() -> bool:
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() < 1:
            return False
    except Exception:
        return False
    if os.name != "nt":
        return True
    for dll in _CUDA_RUNTIME_DLLS:
        try:
            ctypes.WinDLL(dll)
        except OSError:
            LOGGER.info(
                "An NVIDIA GPU is present but %s is not installed; using the CPU", dll
            )
            return False
    return True

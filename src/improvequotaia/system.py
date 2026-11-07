"""Mesures système multi-plateformes : CPU, RAM (psutil) et GPU (selon le matériel et le système).

GPU :
  - NVIDIA (Linux, Windows) : un seul `nvidia-smi -l 1` permanent ;
  - AMD (Linux) : /sys/class/drm/card*/device/gpu_busy_percent ;
  - Apple (macOS) : `ioreg` (« Device Utilization % »), sans droits administrateur ;
  - autres cartes sous Windows : compteurs de performance via PowerShell (CIM, noms non traduits).
"""
from __future__ import annotations

import glob
import re
import shutil
import sys
import threading
import time
from typing import Optional

import psutil

from .utils import fnum, popen_quiet, run_quiet


class GpuReader(threading.Thread):
    name_hint = ""

    def __init__(self):
        super().__init__(daemon=True)
        self.latest: Optional[dict] = None  # {"util", "temp", "power", "vram_used", "vram_total", "name"}
        self.stamp = 0.0
        self.stopped = False

    def publish(self, sample: dict):
        self.latest, self.stamp = sample, time.monotonic()

    def fresh(self) -> Optional[dict]:
        return self.latest if self.latest and time.monotonic() - self.stamp < 8 else None

    def stop(self):
        self.stopped = True


class NullReader(GpuReader):
    def run(self):
        pass


class NvidiaReader(GpuReader):
    FIELDS = "utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,name"

    def __init__(self, exe: str):
        super().__init__()
        self.exe, self.proc = exe, None

    def run(self):
        while not self.stopped:
            try:
                self.proc = popen_quiet([self.exe, f"--query-gpu={self.FIELDS}",
                                         "--format=csv,noheader,nounits", "-l", "1"])
                for line in self.proc.stdout:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 6:
                        self.publish({"util": fnum(parts[0]), "vram_used": fnum(parts[1]),
                                      "vram_total": fnum(parts[2]), "temp": fnum(parts[3]),
                                      "power": fnum(parts[4]), "name": parts[5], "vram_unit": "MiB"})
            except OSError:
                pass
            if not self.stopped:
                time.sleep(5)

    def stop(self):
        super().stop()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


class AmdSysfsReader(GpuReader):
    def __init__(self, device_dir: str):
        super().__init__()
        self.dir = device_dir

    def _read(self, name):
        try:
            with open(f"{self.dir}/{name}") as f:
                return fnum(f.read().strip())
        except OSError:
            return None

    def run(self):
        while not self.stopped:
            used, total = self._read("mem_info_vram_used"), self._read("mem_info_vram_total")
            self.publish({"util": self._read("gpu_busy_percent"), "name": "AMD GPU",
                          "vram_used": used / 2**20 if used else None,
                          "vram_total": total / 2**20 if total else None, "vram_unit": "MiB"})
            time.sleep(1)


class MacIoregReader(GpuReader):
    PATTERN = re.compile(r'"Device Utilization %"\s*=\s*(\d+)')

    def run(self):
        while not self.stopped:
            try:
                out = run_quiet(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"], timeout=5).stdout
                m = self.PATTERN.search(out)
                if m:
                    self.publish({"util": float(m.group(1)), "name": "GPU"})
            except Exception:
                pass
            time.sleep(2)


class WindowsCounterReader(GpuReader):
    SCRIPT = ("(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | "
              "Where-Object { $_.Name -like '*engtype_3D' } | "
              "Measure-Object -Property UtilizationPercentage -Sum).Sum")

    def run(self):
        while not self.stopped:
            try:
                out = run_quiet(["powershell", "-NoProfile", "-NonInteractive", "-Command", self.SCRIPT],
                                timeout=10).stdout.strip()
                value = fnum(out.replace(",", "."))
                if value is not None:
                    self.publish({"util": min(100.0, value), "name": "GPU"})
            except Exception:
                pass
            time.sleep(3)


def make_gpu_reader() -> GpuReader:
    nvsmi = shutil.which("nvidia-smi")
    if nvsmi:
        return NvidiaReader(nvsmi)
    if sys.platform.startswith("linux"):
        for path in sorted(glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")):
            return AmdSysfsReader(path.rsplit("/", 1)[0])
    if sys.platform == "darwin":
        return MacIoregReader()
    if sys.platform == "win32":
        return WindowsCounterReader()
    return NullReader()


def cpu_temperature() -> Optional[float]:
    try:
        temps = psutil.sensors_temperatures()  # Linux / FreeBSD uniquement
    except (AttributeError, OSError):
        return None
    for chip in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
        readings = temps.get(chip)
        if readings:
            pkg = [r for r in readings if r.label.lower().startswith(("package", "tctl", "tdie"))]
            return (pkg or readings)[0].current
    return None


class SystemMonitor:
    def __init__(self):
        psutil.cpu_percent(interval=None)  # amorce la mesure
        self.gpu = make_gpu_reader()
        self.gpu.start()
        self.has_gpu = not isinstance(self.gpu, NullReader)
        self._temp, self._temp_at = None, -1e9

    def read(self) -> dict:
        vm = psutil.virtual_memory()
        used = vm.total - vm.available
        if time.monotonic() - self._temp_at > 5:
            self._temp, self._temp_at = cpu_temperature(), time.monotonic()
        m = {"cpu": psutil.cpu_percent(interval=None) / 100, "cpu_temp": self._temp,
             "cpu_count": psutil.cpu_count(), "ram": used / vm.total, "ram_used": used, "ram_total": vm.total,
             "gpu": None, "vram": None, "gpu_available": self.has_gpu}
        g = self.gpu.fresh()
        if g:
            m["gpu"] = None if g.get("util") is None else g["util"] / 100
            m["gpu_temp"], m["gpu_power"], m["gpu_name"] = g.get("temp"), g.get("power"), g.get("name")
            if g.get("vram_used") is not None and g.get("vram_total"):
                m["vram"] = g["vram_used"] / g["vram_total"]
                m["vram_used"], m["vram_total"] = g["vram_used"], g["vram_total"]
        return m

    def stop(self):
        self.gpu.stop()

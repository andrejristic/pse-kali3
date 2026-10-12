# =============================================================================
# PSE-KALI — LOCAL MODEL DISCOVERY (for the GUI's hot-swap dropdown)
# Lists the .gguf models available on disk and whether each fits free RAM, so
# the human can switch the local model mid-engagement from a dropdown.
# =============================================================================
import os


def ram_free_gb():
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)   # kB -> GB
    except OSError:
        pass
    return 4.0


def list_local_models(models_dir):
    """[{name, path, size_gb, fits}] for every .gguf in models_dir, largest last.
    `fits` = the model file is comfortably under free RAM (with headroom)."""
    out = []
    if not os.path.isdir(models_dir):
        return out
    free = ram_free_gb()
    for f in sorted(os.listdir(models_dir)):
        if f.endswith(".gguf"):
            p = os.path.join(models_dir, f)
            sz = os.path.getsize(p) / (1024 ** 3)
            out.append({"name": f, "path": p, "size_gb": round(sz, 1),
                        "fits": sz < free * 0.9})
    return out

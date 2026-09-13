"""Build-time guard: assert the installed torch carries kernels for target GPUs.
Runs on a CPU-only builder, so it scans the compiled CUDA library.
"""
import pathlib
import re
import sys
import torch

CHUNK = 32 * 1024 * 1024


def compiled_archs():
    lib_dir = pathlib.Path(torch.__file__).parent / "lib"
    libs = sorted(lib_dir.glob("libtorch_cuda*.so")) + sorted(lib_dir.glob("libtorch_cuda*.so.*"))
    if not libs:
        sys.exit(f"no libtorch_cuda found under {lib_dir}")
    found = set()
    pattern = re.compile(rb"sm_(\d{2,3})[af]?")
    for lib in libs:
        with lib.open("rb") as fh:
            tail = b""
            while True:
                block = fh.read(CHUNK)
                if not block:
                    break
                for m in pattern.finditer(tail + block):
                    found.add(f"sm_{m.group(1).decode()}")
                tail = block[-16:]
    return found, [str(p.name) for p in libs]


def main():
    required = sys.argv[1:] or ["sm_120"]
    print(f"torch: {torch.__version__}, cuda: {torch.version.cuda}")
    archs, libs = compiled_archs()
    print(f"scanned: {', '.join(libs)}")
    print(f"compiled archs: {' '.join(sorted(archs, key=lambda a: int(a[3:])))}")
    missing = [a for a in required if a not in archs]
    if missing:
        sys.exit(f"FAIL: torch has no kernels for {', '.join(missing)}")
    print(f"OK: kernels present for {', '.join(required)}")


if __name__ == "__main__":
    main()

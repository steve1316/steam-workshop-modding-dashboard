"""llama.cpp install helpers."""

import io
import zipfile
from pathlib import Path

from backend.routes.llamacpp import _extract_binaries


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_extract_binaries_flattens_exes_and_dlls_and_keeps_the_releases_own_dlls(tmp_path: Path):
    release = _zip({"build/bin/llama-server.exe": b"exe", "build/bin/ggml.dll": b"release", "README.md": b"docs"})
    cudart = _zip({"cudart64.dll": b"cuda", "ggml.dll": b"cudart copy", "notes.txt": b"x"})

    _extract_binaries(tmp_path / "bin", release, cudart)

    files = {p.name: p.read_bytes() for p in (tmp_path / "bin").iterdir()}
    assert files == {"llama-server.exe": b"exe", "ggml.dll": b"release", "cudart64.dll": b"cuda"}

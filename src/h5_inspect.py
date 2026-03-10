# src/h5_inspect.py
from __future__ import annotations
import h5py
from typing import List, Tuple

DEFAULT_KEYWORDS = [
    "angle", "alt", "solar", "sun", "view",
    "azimuth", "zenith", "elev", "height", "gps", "imu"
]

def h5_tree_text(h5_path: str) -> str:
    lines = []

    def _visitor(name, obj):
        if isinstance(obj, h5py.Dataset):
            lines.append(f"[DSET] {name}  shape={obj.shape}  dtype={obj.dtype}")
        else:
            lines.append(f"[GRP ] {name}")

    with h5py.File(h5_path, "r") as f:
        f.visititems(_visitor)

    return "\n".join(lines)

def find_paths(h5_path: str, keywords: List[str] | None = None) -> List[Tuple[str, str]]:
    if keywords is None:
        keywords = DEFAULT_KEYWORDS

    matches = []

    with h5py.File(h5_path, "r") as f:
        def _finder(name, obj):
            lower = name.lower()
            if any(k in lower for k in keywords):
                matches.append((name, type(obj).__name__))
        f.visititems(_finder)

    return matches

def keyword_matches_text(h5_path: str) -> str:
    matches = find_paths(h5_path)
    if not matches:
        return "No keyword matches found."

    lines = ["--- KEYWORD MATCHES ---"]
    for path, typ in matches:
        lines.append(f"{typ:8} {path}")

    return "\n".join(lines)

"""Run the NEON/KSSL builder with conservative project-text site-code parsing."""

from __future__ import annotations

import re

import build_neon_kssl_crosswalk as builder


def explicit_site_code(project_name: object) -> str:
    match = re.search(r"\bNEON[_ ]\d+[_ ]([A-Z0-9]{4})\b", str(project_name or ""))
    return match.group(1) if match else ""


if __name__ == "__main__":
    builder.site_code = explicit_site_code
    builder.main()

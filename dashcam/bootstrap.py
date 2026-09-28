from __future__ import annotations

import os


def bootstrap() -> None:
    if os.environ.get("DASHCAM", "").lower() in ("1", "true", "yes"):
        try:
            from . import instrument

            instrument()
        except Exception:
            pass


def pth_path() -> str:
    import site

    candidates: list[str] = list(site.getsitepackages())
    usersite = site.getusersitepackages()
    if usersite:
        candidates.append(usersite)
    for d in candidates:
        if os.path.isdir(d):
            return os.path.join(d, "dashcam.pth")
    raise RuntimeError("no writable site-packages directory found")


def install() -> str:
    path = pth_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write("import dashcam.bootstrap; dashcam.bootstrap.bootstrap()\n")
    return path


def uninstall() -> str | None:
    path = pth_path()
    if os.path.exists(path):
        os.remove(path)
        return path
    return None


bootstrap()

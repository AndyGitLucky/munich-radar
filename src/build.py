"""Create a Pages-compatible artifact containing only public files."""
import argparse
import json
import shutil
from pathlib import Path


def build(root: Path) -> Path:
    destination = root / "dist"
    destination.mkdir(exist_ok=True)
    (destination / "data").mkdir(exist_ok=True)
    for name in ("index.html", "app.js", "personal.js", "map.js", "topics.js", "style.css", "favicon.svg"):
        shutil.copy2(root / "web" / name, destination / name)
    shutil.copytree(root / "web/vendor", destination / "vendor", dirs_exist_ok=True)
    shutil.copy2(root / "config/places.json", destination / "data/places.json")
    for name in ("events.json", "metadata.json"):
        source = root / "data" / name
        json.loads(source.read_text(encoding="utf-8"))
        shutil.copy2(source, destination / "data" / name)
    (destination / ".nojekyll").touch()
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    build(parser.parse_args().root)

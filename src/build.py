"""Create a Pages-compatible artifact containing only public files."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def build(root: Path, *, atlas=False, atlas_archive=None) -> Path:
    destination = root / "dist"
    destination.mkdir(exist_ok=True)
    (destination / "data").mkdir(exist_ok=True)
    for name in ("index.html", "app.js", "personal.js", "map.js", "topics.js", "occasions.js", "style.css", "favicon.svg"):
        shutil.copy2(root / "web" / name, destination / name)
    # A changed release gets fresh asset URLs even while Safari caches old files.
    index = destination / "index.html"
    html = index.read_text(encoding="utf-8")
    for name in ("app.js", "personal.js", "map.js", "topics.js", "occasions.js", "style.css", "favicon.svg"):
        version = hashlib.sha256((destination / name).read_bytes()).hexdigest()[:12]
        html = html.replace(f'"./{name}"', f'"./{name}?v={version}"')
    index.write_text(html, encoding="utf-8")
    shutil.copytree(root / "web/vendor", destination / "vendor", dirs_exist_ok=True)
    shutil.copy2(root / "config/places.json", destination / "data/places.json")
    for name in ("events.json", "metadata.json"):
        source = root / "data" / name
        json.loads(source.read_text(encoding="utf-8"))
        shutil.copy2(source, destination / "data" / name)
    (destination / ".nojekyll").touch()
    if atlas:
        from .map_pipeline.public import export_site
        export_site(root,destination,atlas_archive)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--atlas',action='store_true')
    parser.add_argument('--atlas-archive',type=Path)
    args=parser.parse_args()
    build(args.root,atlas=args.atlas,atlas_archive=args.atlas_archive)

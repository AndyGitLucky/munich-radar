import re
from pathlib import Path
from shutil import copytree

from src.build import build


def test_changed_assets_get_new_urls_and_unchanged_assets_keep_their_version(tmp_path):
    root = Path(__file__).parents[1]
    for directory in ("web", "config", "data"):
        copytree(root / directory, tmp_path / directory)
    index = build(tmp_path) / "index.html"
    first = index.read_text(encoding="utf-8")
    def url(html, name):
        return re.search(rf'"(\./{re.escape(name)}\?v=[a-f0-9]{{12}})"', html).group(1)
    before = url(first, "app.js")
    stylesheet = url(first, "style.css")
    assert index.read_text(encoding="utf-8") == (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    app = tmp_path / "web/app.js"
    app.write_text(app.read_text(encoding="utf-8") + "\n// New release\n", encoding="utf-8")
    second = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert url(second, "app.js") != before
    assert url(second, "style.css") == stylesheet
    assert '"./app.js"' in (tmp_path / "web/index.html").read_text(encoding="utf-8")

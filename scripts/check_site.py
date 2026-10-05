"""Offline smoke checks for the static site; not a full HTML validator."""

from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = set()
        self.doctype = False
        self.title = []
        self.in_title = False
        self.json_data = None
        self.links = []

    def handle_decl(self, decl):
        if decl.lower() == "doctype html":
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.json_data = []
        for attr in ("href", "src"):
            if attrs.get(attr):
                self.links.append(attrs[attr])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.json_data is not None:
            json.loads("".join(self.json_data))
            self.json_data = None

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.json_data is not None:
            self.json_data.append(data)


def check_page(root, path):
    page = Page()
    page.feed(path.read_text(encoding="utf-8"))
    page.close()
    if not page.doctype or not {"html", "head", "title", "body"} <= page.tags:
        raise ValueError(f"{path}: missing HTML document structure")
    if not "".join(page.title).strip():
        raise ValueError(f"{path}: empty title")
    if page.json_data is not None:
        raise ValueError(f"{path}: unclosed JSON-LD script")
    for link in page.links:
        url = urlsplit(link)
        if url.scheme or url.netloc or not url.path:
            continue
        target = ((root / unquote(url.path).lstrip("/")) if url.path.startswith("/")
                  else (path.parent / unquote(url.path))).resolve()
        if root.resolve() not in (target, *target.parents):
            raise ValueError(f"{path}: local link escapes the site: {link}")
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            raise ValueError(f"{path}: missing local href/src target: {link}")


def main():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE)
    pages = {ROOT / name for name in result.stdout.decode().split("\0")
             if name.endswith(".html") and (ROOT / name).is_file()}
    for required in (ROOT / "index.html", ROOT / "website/index.html"):
        if required not in pages:
            raise ValueError(f"Missing required page: {required}")
    for path in sorted(pages):
        check_page(ROOT, path)
    print(f"Static site checks passed ({len(pages)} HTML pages).")


if __name__ == "__main__":
    main()

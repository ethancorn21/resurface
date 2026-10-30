"""Pack the public copy (dist/public, from tools/export_public.py) for speed: minified code, content-named files cached for
a year, and a _headers file for Cloudflare.

usage: called by tools/export_public.py (skip with --no-pack); alone: .venv/bin/python tools/pack_public.py [dist/public]

What it does to the copy, in place:
  - minifies the page's inline <script> and <style> blocks, arrive.js, config.js, pmtiles and the MapLibre stylesheet
    with esbuild (comments dropped, local names mangled; top-level names kept, because the page's classic scripts share
    one global scope). maplibre-gl and three.js ship already minified and are left as they are.
  - inlines vendor/fonts.css into the page (one request fewer before the first paint)
  - splits the sites' summaries out of the page's copy of the site index (data/sites-text.json, fetched once the first
    view is in) and rounds its coordinates to 7 decimals: half the index, and nothing the map or the list needs
  - moves every script, stylesheet, font and data index the page asks for by a fixed name into _/ under a content
    hash (_/maplibre-gl-5.6.0.3f9c1a2b7d.js), rewrites the page's references, and serves _/ as immutable: a returning
    visitor asks for nothing but the page itself until a file really changes
  - drops HTML comments from the page
  - writes _headers: _/ for a year; the site images under data/sites/ for a day, served stale for a week while they
    revalidate (their names are fixed, so they cannot be immutable); the page itself revalidates on every visit

esbuild: $ESBUILD, else esbuild on PATH, else the one wrangler installed in ../digitalgarden/node_modules, else npx.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# files the page names, hashed into _/; (path in the copy, minify loader or None)
HASHED = [
    ("config.js", "js"),
    ("arrive.js", "js"),
    ("vendor/maplibre-gl-5.6.0.js", None),
    ("vendor/maplibre-gl-5.6.0.css", "css"),
    ("vendor/pmtiles-3.2.1.js", "js"),
    ("vendor/three-r128.min.js", None),
    ("data/sites-text.json", None),  # made by split_sites below
    ("data/sites.json", None),
    ("data/catalog.json", None),
    ("data/align.json", None),
]
# kept under their plain names too: other pages may read the data indexes (the plain sites.json stays whole)
KEEP_PLAIN = {"data/sites.json", "data/catalog.json"}

HEADERS = """\
# written by tools/pack_public.py
/_/*
  Cache-Control: public, max-age=31536000, immutable
/data/sites/*
  Cache-Control: public, max-age=86400, stale-while-revalidate=604800
/
  Cache-Control: no-cache
/index.html
  Cache-Control: no-cache
"""


def find_esbuild():
    for c in (os.environ.get("ESBUILD"), shutil.which("esbuild"),
              os.path.join(ROOT, "..", "digitalgarden", "node_modules", ".bin", "esbuild")):
        if c and os.path.exists(c):
            return [c]
    if shutil.which("npx"):
        return ["npx", "--yes", "esbuild@0.25.12"]
    sys.exit("pack: no esbuild (set ESBUILD, or npm i -g esbuild); --no-pack builds without it")


def minify(esbuild, code, loader):
    r = subprocess.run(esbuild + [f"--loader={loader}", "--minify", "--legal-comments=none", "--log-level=error"],
                       input=code.encode(), capture_output=True)
    if r.returncode:
        sys.exit(f"pack: esbuild failed on a {loader} block:\n{r.stderr.decode()}")
    return r.stdout.decode().strip()


def short_hash(data):
    return hashlib.sha256(data).hexdigest()[:10]


def hashed_name(rel, data):
    stem, ext = os.path.splitext(os.path.basename(rel))
    return f"_/{stem}.{short_hash(data)}{ext}"


def put(out, rel, data):
    p = os.path.join(out, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def refs(page, rel):
    """the page's references to rel: a quoted, parenthesised or template-literal path (an optional ?query after it)"""
    return re.compile(r"(?<=[\"'(`])" + re.escape(rel) + r"(?=[\"'?)`])")


def _round(o, nd=7):
    """floats to nd decimals (7: about a centimetre in degrees): the corners were written with 15"""
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, list):
        return [_round(x, nd) for x in o]
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    return o


def split_sites(out):
    """the page's copy of the site index without the summaries (a third of it, and nothing the map or the list shows),
    which go to data/sites-text.json, fetched later (the page's loadText); returns (index bytes, plain bytes)"""
    with open(os.path.join(out, "data", "sites.json"), "rb") as f:
        plain = f.read()
    sites = json.loads(plain)["sites"]
    text = {s["id"]: s.pop("summary") for s in sites if s.get("summary")}
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode()
    put(out, "data/sites-text.json", dump(text))
    return dump({"sites": _round(sites), "text": True}), plain


def pack(out, esbuild=None):
    esbuild = esbuild or find_esbuild()
    page_path = os.path.join(out, "index.html")
    with open(page_path) as f:
        page = f.read()

    # fonts.css: inlined, each font moved into _/ under its hash
    fonts_css_path = os.path.join(out, "vendor", "fonts.css")
    with open(fonts_css_path) as f:
        fonts_css = f.read()
    font_names = {}
    for rel in sorted(set(re.findall(r"url\((fonts/[^)]+\.woff2)\)", fonts_css))):
        with open(os.path.join(out, "vendor", rel), "rb") as f:
            data = f.read()
        font_names["vendor/" + rel] = name = hashed_name(rel, data)
        put(out, name, data)
        fonts_css = fonts_css.replace(f"url({rel})", f"url({name})")
    link = '<link rel="stylesheet" href="vendor/fonts.css">'
    if page.count(link) != 1:
        sys.exit("pack: the page no longer links vendor/fonts.css exactly once")
    page = page.replace(link, "<style>" + minify(esbuild, fonts_css, "css") + "</style>")

    # the page's own code
    def block(tag, loader):
        def sub(m):
            return f"<{tag}>" + minify(esbuild, m.group(1), loader) + f"</{tag}>"
        return re.compile(rf"<{tag}>(.*?)</{tag}>", re.S), sub
    for tag, loader in (("script", "js"), ("style", "css")):
        rx, sub = block(tag, loader)
        page = rx.sub(sub, page)

    # comments, outside the code blocks (all of them are minified by now, so none holds a "<!--")
    page = re.sub(r"<!--.*?-->\n?", "", page, flags=re.S)

    # the named files
    names = dict(font_names)
    index, plain_sites = split_sites(out)
    for rel, loader in HASHED:
        p = os.path.join(out, rel)
        if not os.path.exists(p):
            sys.exit(f"pack: {rel} is missing from the copy")
        with open(p, "rb") as f:
            data = f.read()
        if loader:
            data = minify(esbuild, data.decode(), loader).encode()
        if rel == "data/sites.json":
            data = index
        names[rel] = name = hashed_name(rel, data)
        put(out, name, data)
        if rel not in KEEP_PLAIN:
            os.remove(p)
    put(out, "data/sites.json", plain_sites)
    for rel, name in names.items():
        page, n = refs(page, rel).subn(name, page)
        if not n and rel not in font_names:
            sys.exit(f"pack: the page never names {rel}: update HASHED in tools/pack_public.py")
    os.remove(fonts_css_path)
    shutil.rmtree(os.path.join(out, "vendor", "fonts"))
    if not os.listdir(os.path.join(out, "vendor")):
        os.rmdir(os.path.join(out, "vendor"))
    left = [x for x in re.findall(r"(?:src|href)=\"((?:vendor/|data/)[^\"]+)\"", page) if "${" not in x]  # not templates
    if left:
        sys.exit(f"pack: the page still names unpacked files: {left}")

    with open(page_path, "w") as f:
        f.write(page)
    with open(os.path.join(out, "_headers"), "w") as f:
        f.write(HEADERS)
    return names


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "public")
    for rel, name in pack(out).items():
        print(f"  {rel} -> {name}")

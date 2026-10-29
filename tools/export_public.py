"""Build the public, read-only copy of the site (resurface.ethanlawcorn.com) into dist/public/.

usage: .venv/bin/python tools/export_public.py [--out dist/public] [--no-pack]

The LAN copy (server/serve.py) is the owner's: it writes fits, reviews and Finder marks. The public copy is static
files only, so it carries none of that:
  - the page and the local scripts it includes (arrive.js), vendor/
  - no owner tools: review.js, fitqueue.js, fitkit.js, test.html are not copied, and config.js sets public: true,
    which makes the page skip them, the Finder tab, plate/drawing nudges and the plan pictures (web/index.html PUBLIC)
  - no private data: web/data/scan, scans.json, amazon, fit_queue.json, review.json, plans.json, and nothing from
    data/ (db, raw, finder) is copied except the saved nudges below
  - only the site files the page draws: relief.jpg, block_h.png, block_top.jpg, imagery.jpg, the plate images, and
    every old map and drawing in depictions.json
  - data/align.json: the hand-saved plate and drawing nudges (data/db plates, depalign), read-only
  - config.js comes from deploy/config.js (gitignored: the Esri key) with public: true added
  - no dev canvas (devkit.js and its tag): tuning happens on the local page, the live page carries none of it
  - then tools/pack_public.py: minified code, content-named files under _/ cached for a year, _headers
    (--no-pack leaves the copy readable, for debugging a build; never deploy it)

Every old map and drawing is published. The maps are 150+ years old (OS six-inch 1840s-1900s, Roy 1747-55, TMK 1850,
Cassini, Etat-major), so the works themselves are public domain, and a faithful scan of a public-domain 2D work adds no
new copyright (UK IPO guidance; EU DSM Directive art. 14, in force in NL/FR/DE). Each overlay keeps its source credit
in the site panel. Contrast the modern Esri aerial, which is copyrighted and served under its own key and terms.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import build_site  # noqa: E402  (marks: the marker fields, recomputed from what the public copy shows)

SITE_FILES = ("relief.jpg", "block_h.png", "block_top.jpg", "imagery.jpg")
WEB_DATA = ("sites.json", "catalog.json")


def dep_files(d):
    out = [d.get("file"), d.get("ink")]
    ck = d.get("check")
    if isinstance(ck, dict):
        out += [ck.get("file"), ck.get("ink")]
    return [f for f in out if f]


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "dist", "public"))
    ap.add_argument("--no-pack", action="store_true", help="skip tools/pack_public.py (readable copy; not for deploy)")
    ap.add_argument("--relief", default=os.environ.get("RESURFACE_RELIEF"),
                    help="URL of the relief index (tools/prerender_relief.py pack); none = no relief between sites")
    a = ap.parse_args(argv)
    out = a.out
    cfg_src = os.path.join(ROOT, "deploy", "config.js")
    if not os.path.exists(cfg_src):
        sys.exit("deploy/config.js is missing (the Esri key): see web/index.html SAT_TILES")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    # the page without the dev canvas's tag (and its comment); the file itself is not copied below
    with open(os.path.join(WEB, "index.html")) as f:
        page = f.read()
    page, n = re.subn(r'(?:<!--[^>]*-->\n)?<script src="devkit\.js"></script>\n?', "", page)
    if n != 1:
        sys.exit("the page no longer includes devkit.js exactly once: update the dev canvas strip in export_public.py")
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write(page)
    # every local script the page includes (arrive.js, ...): read from the page itself, so a new one ships without
    # editing this list; config.js is written below, vendor/ copied whole. The owner tools are not <script src>
    # includes (the page injects them only when not public), so they never match.
    for src in sorted(set(re.findall(r'<script src="([^":/]+\.js)"', page)) - {"config.js"}):
        copy(os.path.join(WEB, src), os.path.join(out, src))
    copy(os.path.join(WEB, "arrive.js"), os.path.join(out, "arrive.js"))  # hand-off from the ethanlawcorn.com hub
    shutil.copytree(os.path.join(WEB, "vendor"), os.path.join(out, "vendor"))
    with open(cfg_src) as f:
        cfg = f.read()
    with open(os.path.join(out, "config.js"), "w") as f:
        f.write(cfg.rstrip("\n") + "\nwindow.RESURFACE.public = true;\n")
        if a.relief:  # the pre-rendered relief index (tools/prerender_relief.py pack), archives on R2
            f.write(f"window.RESURFACE.reliefTiles = {json.dumps(a.relief)};\n")
    for name in WEB_DATA:
        p = os.path.join(WEB, "data", name)
        if os.path.exists(p) and name != "sites.json":
            copy(p, os.path.join(out, "data", name))

    with open(os.path.join(WEB, "data", "sites.json")) as f:
        index = json.load(f)
    kept_deps, missing = 0, []
    for s in index["sites"]:
        sid = s["id"]
        src_dir = os.path.join(WEB, "data", "sites", sid)
        dst_dir = os.path.join(out, "data", "sites", sid)
        for name in SITE_FILES:
            if os.path.exists(os.path.join(src_dir, name)):
                copy(os.path.join(src_dir, name), os.path.join(dst_dir, name))
        plate = s.get("plate")
        if isinstance(plate, dict):
            for k in ("ink", "paper"):
                if plate.get(k):
                    p = os.path.join(src_dir, plate[k])
                    (copy(p, os.path.join(dst_dir, plate[k])) if os.path.exists(p) else missing.append(f"{sid}/{plate[k]}"))
        dj = os.path.join(src_dir, "depictions.json")
        if not os.path.exists(dj):
            continue
        with open(dj) as f:
            doc = json.load(f)
        keep = []
        for d in doc.get("depictions", []):
            for name in dep_files(d):
                p = os.path.join(src_dir, name)
                (copy(p, os.path.join(dst_dir, name)) if os.path.exists(p) else missing.append(f"{sid}/{name}"))
            keep.append(d)
        kept_deps += len(keep)
        doc["depictions"] = keep
        os.makedirs(dst_dir, exist_ok=True)
        with open(os.path.join(dst_dir, "depictions.json"), "w") as f:
            json.dump(doc, f, separators=(",", ":"))
    # the saved nudges (plate and drawing positions moved by hand in the owner's copy) live in the server's db and the
    # page applies them on load; the public copy has no server, so it gets a read-only snapshot of exactly those two
    align = {}
    for coll in ("plates", "depalign"):
        d = os.path.join(ROOT, "data", "db", coll)
        align[coll] = {f[:-5]: json.load(open(os.path.join(d, f)))
                       for f in sorted(os.listdir(d)) if f.endswith(".json")} if os.path.isdir(d) else {}
    with open(os.path.join(out, "data", "align.json"), "w") as f:
        json.dump(align, f, separators=(",", ":"))
    # the markers (red square, size, colour, oldest, overlay count) count what the public copy shows: a site whose
    # only old map was left out loses it. build_site reads <root>/web/data/sites, so point a temp root at the copy.
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "web", "data"))
        os.symlink(os.path.join(out, "data", "sites"), os.path.join(tmp, "web", "data", "sites"))
        for s in index["sites"]:
            build_site.marks(s, root=tmp)
    with open(os.path.join(out, "data", "sites.json"), "w") as f:
        json.dump(index, f, separators=(",", ":"))
    if not a.no_pack:
        import pack_public  # noqa: E402  (tools/, next to this file)
        pack_public.pack(out)

    n_files = sum(len(fs) for _, _, fs in os.walk(out))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(out) for f in fs)
    big = [os.path.relpath(os.path.join(r, f), out) for r, _, fs in os.walk(out) for f in fs
           if os.path.getsize(os.path.join(r, f)) > 25 * 1024 * 1024]
    print(f"public copy: {out}")
    print(f"  sites {len(index['sites'])}, depictions {kept_deps}")
    print(f"  files {n_files}, {size / 1e6:.0f} MB; over 25 MiB: {big or 'none'}")
    if missing:
        print(f"  MISSING source files ({len(missing)}): {missing[:10]}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

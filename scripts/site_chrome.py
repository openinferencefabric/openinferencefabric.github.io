#!/usr/bin/env python3
"""Write the same header and footer into every page, so the menu stays identical everywhere.

Edit NAV or FOOT here, then run:  python scripts/site_chrome.py
Each page keeps its own content between the markers; the header goes between <!-- site-head --> and
<!-- /site-head -->, the footer between <!-- site-foot --> and <!-- /site-foot -->.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = {"index.html": ("", "home"), "roadmap/index.html": ("../", "roadmap"), "upstream/index.html": ("../", "upstream")}

# (label, target, key); target "#x" is a section of the home page, a path is a page of this site
NAV = [
    ("The stack", "#stack", "stack"),
    ("How it works", "#architecture", "architecture"),
    ("NVIDIA + AMD", "#amd", "amd"),
    ("Roadmap", "roadmap/", "roadmap"),
    ("Upstream work", "upstream/", "upstream"),
    ("Contribute", "#contribute", "contribute"),
    ("GitHub ↗", "https://github.com/openinferencefabric/oif", "github"),
]
CONTACT = "manmohan@openinferencefabric.us.ci"

def mark(loop=False, label=None):
    """The OIF mark, animated (site.css .wv), drawn in the page's colour tokens so it follows light and dark."""
    f = lambda v: f'style="fill:var(--{v})"'
    dots = "".join(f'<circle class="wv-x wv-tok {r} t{k}" cx="{x}" cy="{y}" r="{rad}" {f("ink")}/>'
                   for r, y in (("r1", 37.5), ("r2", 63.5)) for k, (x, rad) in enumerate(((96, 7.5), (113, 5), (125, 3)), 1))
    aria = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true"'
    return (f'<svg class="wv{" wv-loop" if loop else ""}" viewBox="0 0 132 100" {aria}>'
            f'<rect class="wv-x wv-warp" x="26" y="12" width="15" height="76" rx="7.5" {f("teal")}/>'
            f'<rect class="wv-x wv-warp s" x="54" y="12" width="15" height="76" rx="7.5" {f("saffron")}/>'
            f'<g class="wv-x wv-weft"><rect x="8" y="27" width="76" height="21" {f("bg")}/><rect x="8" y="30" width="76" height="15" rx="7.5" {f("ink")}/></g>'
            f'<g class="wv-x wv-weft b"><rect x="8" y="53" width="76" height="21" {f("bg")}/><rect x="8" y="56" width="76" height="15" rx="7.5" {f("ink")}/></g>'
            f'<g class="wv-x wv-cross"><rect x="51" y="29" width="21" height="17" {f("bg")}/><rect x="54" y="28" width="15" height="19" {f("saffron")}/></g>'
            f'<g class="wv-x wv-cross b"><rect x="23" y="55" width="21" height="17" {f("bg")}/><rect x="26" y="54" width="15" height="19" {f("teal")}/></g>'
            f'{dots}</svg>')


def head(up, page):
    links = []
    for label, target, key in NAV:
        href = target if target.startswith("http") or page == "home" else up + target
        attrs = ' aria-current="page"' if key == page else ""
        if key == "amd":
            links.append(f'<a class="duo" href="{href}"><i></i>{label}</a>')
        else:
            links.append(f'<a href="{href}"{attrs}>{label}</a>')
    nav = "\n      ".join(links)
    return (f'<header class="site-head"><div class="site-in">\n'
            f'    <a class="site-brand" href="{up or "./"}" aria-label="Open Inference Fabric home">{mark()}<b>open inference <span>fabric</span></b></a>\n'
            f'    <nav class="site-nav" aria-label="Main">\n      {nav}\n    </nav>\n'
            f'</div></header>')


def foot(up):
    return ('<footer class="site-foot"><div class="site-in">\n'
            '    <span>Open Inference Fabric · Apache-2.0 · run by volunteers</span>\n'
            f'    <a href="mailto:{CONTACT}">{CONTACT}</a>\n'
            '    <a href="https://github.com/openinferencefabric">GitHub</a>\n'
            '    <a href="https://github.com/openinferencefabric/oif/blob/main/CODE_OF_CONDUCT.md">Code of conduct</a>\n'
            '    <a href="https://github.com/openinferencefabric/oif/blob/main/docs/SECURITY.md">Security</a>\n'
            '    <span class="tm">NVIDIA, Run:ai, AMD, Radeon, Google, Broadcom and Marvell are trademarks of their owners; this project is not affiliated with them.</span>\n'
            '</div></footer>')


def put(text, name, block):
    pat = re.compile(rf"<!-- {name} -->.*?<!-- /{name} -->", re.S)
    if not pat.search(text):
        raise SystemExit(f"marker <!-- {name} --> missing")
    return pat.sub(lambda _: f"<!-- {name} -->\n{block}\n<!-- /{name} -->", text)


for rel, (up, page) in PAGES.items():
    p = ROOT / rel
    raw = p.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s = put(s, "site-head", head(up, page))
    s = put(s, "site-foot", foot(up))
    if page == "home":
        s = put(s, "hero-mark", mark(loop=True, label="Open Inference Fabric logo"))
    p.write_text(s, encoding="utf-8", newline=nl)
    print("updated", rel)

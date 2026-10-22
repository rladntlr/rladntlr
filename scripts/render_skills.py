"""Render transparent glass skill icons and their README layout.

python scripts/render_skills.py --fetch --write-readme --browser-channel chrome
Subsequent renders use the saved SVG logos and do not need --fetch.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "skills"
SOURCES = ASSETS / "source"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)

# slug, caption, source logo, glass tint
SKILLS = [
    ("java", "Java", "java", "#f59a38"),
    ("python", "Python", "python", "#669ddd"),
    ("cplusplus", "C++", "cplusplus", "#719fdf"),
    ("springboot", "Spring Boot", "springboot", "#88c86b"),
    ("mysql", "MySQL", "mysql", "#77b9da"),
    ("pytorch", "PyTorch", "pytorch", "#f0785c"),
    ("huggingface", "Hugging Face", "huggingface", "#f2c24b"),
    ("scikitlearn", "scikit-learn", "scikitlearn", "#f7a55a"),
    ("jupyter", "Jupyter", "jupyter", "#f39a4a"),
    ("git", "Git", "git", "#f08066"),
    ("github", "GitHub", "github", "#a9b4c4"),
]
GROUPS = [
    ("### Languages", ["java", "python", "cplusplus"]),
    ("### Backend", ["springboot", "mysql"]),
    ("### AI / Data", ["pytorch", "huggingface", "scikitlearn", "jupyter"]),
    ("### Tools", ["git", "github"]),
]
DEVICON = {
    "java": "java/java-original.svg",
}
CUSTOM = {
    "jpa": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 64"><path fill-rule="evenodd" d="M8 10h7v31c0 9-4 14-13 14v-7c4 0 6-2 6-7zm14 0h13c11 0 17 6 17 16S46 42 35 42h-6v13h-7zm7 7v18h6c6 0 10-3 10-9s-4-9-10-9zm25 38L69 10h8l15 45h-8l-4-12H66l-4 12zm14-19h10l-5-16z"/></svg>',
    "websocket": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M11 13h28l-7-7 5-5 16 16-16 16-5-5 7-7H11zm42 38H25l7 7-5 5-16-16 16-16 5 5-7 7h28z"/></svg>',
    "http-sse": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M4 12h56v7H4zm0 17h38l-7-7 5-5 16 16-16 16-5-5 8-8H4zm0 18h19v7H4z"/></svg>',
}


def fetch_sources():
    SOURCES.mkdir(parents=True, exist_ok=True)
    needed = sorted({source for _, _, source, _ in SKILLS})

    def fetch(source):
        if source in CUSTOM:
            content = CUSTOM[source]
        else:
            url = (f"https://raw.githubusercontent.com/devicons/devicon/master/icons/{DEVICON[source]}"
                   if source in DEVICON else
                   f"https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{source}.svg")
            with urlopen(Request(url, headers={"User-Agent": "profile-renderer"}), timeout=30) as response:
                content = response.read().decode("utf-8")
        ET.fromstring(content)
        (SOURCES / f"{source}.svg").write_text(content, encoding="utf-8")
        return source

    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = list(pool.map(fetch, needed))
    print(f"Saved {len(fetched)} source marks.")


def mix(color, amount):
    return "#" + "".join(f"{round(int(color[i:i+2], 16) * (1-amount) + 255 * amount):02x}" for i in (1, 3, 5))


def symbol(source):
    root = ET.parse(SOURCES / f"{source}.svg").getroot()
    mark = ET.Element(f"{{{NS}}}symbol", {"id": "mark", "viewBox": root.get("viewBox", "0 0 24 24")})
    # Keep source geometry and transforms; pass each layer's glass fill through
    # the symbol instead of retaining the original flat brand fills.
    for child in root:
        if child.tag.rsplit("}", 1)[-1] in {"title", "desc", "defs", "style"}:
            continue
        clone = deepcopy(child)
        for node in clone.iter():
            for attribute in ("class", "style", "fill", "stroke"):
                node.attrib.pop(attribute, None)
            node.set("fill", "inherit")
        mark.append(clone)
    return ET.tostring(mark, encoding="unicode")


def icon(skill, theme):
    slug, caption, source, tint = skill
    dark = theme == "dark"
    ink = "#e4eaf3" if dark else "#27364b"
    tint = tint if dark else "#" + "".join(f"{round(int(tint[i:i+2],16)*0.80):02x}" for i in (1, 3, 5))
    plate = "#ffffff" if dark else "#dce5f2"
    mark = symbol(source)
    lines = ["Kotlin", "Coroutines"] if slug == "coroutines" else [caption]
    # 84/192 == 56/128: the artwork stays at its previous displayed size.
    # A wider caption canvas restores readable 11.4px names independently.
    labels = "".join(f'<text x="96" y="{140+i*28}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="26" font-weight="500" fill="{ink}">{escape(line)}</text>' for i, line in enumerate(lines))
    extra = ('<ellipse cx="64" cy="59" rx="31" ry="12" transform="rotate(-28 64 59)" stroke="url(#rim)" stroke-width="1.3"/>'
             if slug == "coroutines" else "")
    return f'''<svg xmlns="{NS}" width="192" height="182" viewBox="0 0 192 182" fill="none" role="img" aria-labelledby="title">
<title id="title">{escape(caption)}</title>
<defs>
  {mark}
  <linearGradient id="surface" x1="20" y1="10" x2="100" y2="111" gradientUnits="userSpaceOnUse">
    <stop stop-color="{plate}" stop-opacity="{'.21' if dark else '.57'}"/>
    <stop offset=".42" stop-color="{plate}" stop-opacity="{'.055' if dark else '.22'}"/>
    <stop offset="1" stop-color="{tint}" stop-opacity="{'.12' if dark else '.11'}"/>
  </linearGradient>
  <linearGradient id="rim" x1="22" y1="12" x2="99" y2="110" gradientUnits="userSpaceOnUse">
    <stop stop-color="white" stop-opacity="{'.82' if dark else '.98'}"/>
    <stop offset=".30" stop-color="white" stop-opacity=".14"/>
    <stop offset=".64" stop-color="{tint}" stop-opacity=".12"/>
    <stop offset="1" stop-color="white" stop-opacity="{'.6' if dark else '.95'}"/>
  </linearGradient>
  <linearGradient id="logo" x1="0" y1="0" x2="1" y2="1" gradientUnits="objectBoundingBox">
    <stop stop-color="{mix(tint,.78 if dark else .46)}"/>
    <stop offset=".38" stop-color="{mix(tint,.18)}" stop-opacity=".95"/>
    <stop offset=".70" stop-color="{tint}" stop-opacity=".83"/>
    <stop offset="1" stop-color="{mix(tint,.56 if dark else .20)}"/>
  </linearGradient>
  <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="1" gradientUnits="objectBoundingBox">
    <stop stop-color="white" stop-opacity="{'.73' if dark else '.40'}"/><stop offset=".4" stop-color="white" stop-opacity="0"/><stop offset=".8" stop-color="white" stop-opacity="0"/><stop offset="1" stop-color="white" stop-opacity=".18"/>
  </linearGradient>
  <filter id="halo" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="13"/></filter>
  <filter id="shadow" x="-60%" y="-60%" width="220%" height="240%"><feDropShadow dx="0" dy="6" stdDeviation="5" flood-color="{tint if dark else '#5c7092'}" flood-opacity="{'.18' if dark else '.16'}"/></filter>
  <filter id="depth" x="-40%" y="-40%" width="180%" height="200%"><feDropShadow dx="0" dy="2" stdDeviation="1.4" flood-color="{tint}" flood-opacity=".36"/></filter>
  <clipPath id="squircle"><rect x="14" y="10" width="100" height="100" rx="27"/></clipPath>
</defs>
<g transform="translate(32 0)">
<rect x="14.5" y="10.5" width="99" height="99" rx="27" fill="url(#surface)" filter="url(#shadow)"/>
<g clip-path="url(#squircle)">
  <ellipse cx="44" cy="83" rx="28" ry="20" fill="{tint}" fill-opacity="{'.30' if dark else '.16'}" filter="url(#halo)"/>
  <ellipse cx="99" cy="19" rx="29" ry="17" fill="white" fill-opacity="{'.15' if dark else '.65'}" filter="url(#halo)"/>
  <path d="M13 46C42 21 76 44 115 20V10H14Z" fill="white" fill-opacity="{'.035' if dark else '.24'}"/>
</g>
<rect x="14.5" y="10.5" width="99" height="99" rx="27" stroke="url(#rim)" stroke-width="1.15"/>
<rect x="16.8" y="12.8" width="94.4" height="94.4" rx="25" stroke="white" stroke-opacity="{'.06' if dark else '.30'}" stroke-width=".6"/>
<path d="M25 30C27 22 32 19 40 18" stroke="white" stroke-opacity="{'.65' if dark else '.95'}" stroke-width="1.3" stroke-linecap="round"/>
<path d="M89 103C97 102 104 97 107 88" stroke="{mix(tint,.6)}" stroke-opacity=".45" stroke-width="1.2" stroke-linecap="round"/>
<g filter="url(#depth)">
  <use href="#mark" x="34" y="31" width="60" height="60" fill="{tint}" opacity=".43" transform="translate(0 1.7)"/>
  <use href="#mark" x="34" y="29" width="60" height="60" fill="url(#logo)"/>
  <use href="#mark" x="34" y="28.5" width="60" height="60" fill="url(#sheen)"/>
</g>
{extra}
</g>
{labels}
</svg>\n'''


def skills_markdown():
    by_slug = {slug: caption for slug, caption, _, _ in SKILLS}
    result = ["## 🛠️ Skills", "<!-- Glass icons: scripts/render_skills.py -->"]
    for heading, slugs in GROUPS:
        result.extend(["", heading, "", "<p>"])
        for slug in slugs:
            result.append(f'''  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/skills/{slug}-glass-dark.png">
    <img src="assets/skills/{slug}-glass-light.png" width="84" alt="{escape(by_slug[slug])}">
  </picture>''')
        result.append("</p>")
    return "\n".join(result) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--write-readme", action="store_true")
    parser.add_argument("--browser-channel", default=None)
    args = parser.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    if args.fetch:
        fetch_sources()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.browser_channel, headless=True)
        page = browser.new_page(viewport={"width": 192, "height": 182}, device_scale_factor=3)
        for skill in SKILLS:
            for theme in ("dark", "light"):
                source = icon(skill, theme)
                ET.fromstring(source)
                path = ASSETS / f"{skill[0]}-glass-{theme}.svg"
                path.write_text(source, encoding="utf-8")
                page.set_content('<style>body{margin:0;background:transparent}</style>' + source)
                assert page.locator('symbol > *').count() > 0, skill[0]
                clipped = page.locator('svg > text').evaluate_all('''nodes => nodes.filter(node => {
                    const b = node.getBBox(); return b.x < 0 || b.x + b.width > 192 || b.y + b.height > 182;
                }).map(node => node.textContent)''')
                assert not clipped, (skill[0], clipped)
                page.locator("svg").first.screenshot(path=str(path.with_suffix(".png")), omit_background=True)
        browser.close()
    if args.write_readme:
        readme = ROOT / "README.md"
        before = readme.read_text(encoding="utf-8").split("## 🛠️ Skills", 1)[0]
        readme.write_text(before + skills_markdown(), encoding="utf-8")
    print(f"Rendered {len(SKILLS)} glass icons in both themes.")


if __name__ == "__main__":
    main()

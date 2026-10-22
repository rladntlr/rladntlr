"""Render a custom GitHub Insights dashboard from the GitHub GraphQL API.

Run with --refresh to fetch a new snapshot (needs GITHUB_TOKEN; the Actions
token is enough). Without it, render the saved snapshot. The isometric
calendar is drawn here from real contribution counts; nothing is invented.
"""

import argparse
from datetime import datetime
from html import escape
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SNAPSHOT = ASSETS / "github-metrics-data.json"
USER = "rladntlr"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
QUERY = """
query($login: String!) {
  user(login: $login) {
    pullRequests { totalCount }
    merged: pullRequests(states: MERGED) { totalCount }
    issues { totalCount }
    openIssues: issues(states: OPEN) { totalCount }
    closedIssues: issues(states: CLOSED) { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes { languages(first: 20) { edges { size node { name color } } } }
    }
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}
"""


def validate(data):
    languages, calendar = data["languages"], data["calendar"]
    assert languages["stats"], "No language data"
    assert sum(languages["stats"].values()) == languages["total"]
    assert min(data["pr"]["count"], data["issues"]["count"]) >= 0
    assert len(calendar["days"]) >= 350, "Calendar does not cover a year"
    return data


def summarize(days):
    counts = [day["count"] for day in days]
    streak = best = 0
    for count in counts:
        streak = streak + 1 if count else 0
        best = max(best, streak)
    return {"days": days, "streak": {"max": best}, "average": f"{sum(counts) / len(counts):.2f}", "max": max(counts)}


def refresh():
    token = os.environ.get("GITHUB_TOKEN")
    assert token, "GITHUB_TOKEN is not set"
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-renderer"},
    )
    with urlopen(request, timeout=60) as response:
        body = json.load(response)
    assert not body.get("errors"), body.get("errors")
    user = body["data"]["user"]
    stats, colors = {}, {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            stats[name] = stats.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    days = [
        {"date": day["date"], "weekday": day["weekday"], "count": day["contributionCount"],
         "level": LEVELS.index(day["contributionLevel"])}
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]
        for day in week["contributionDays"]
    ]
    data = {
        "source": "https://api.github.com/graphql",
        "user": USER,
        "languages": {"stats": stats, "colors": colors, "total": sum(stats.values())},
        "pr": {"count": user["pullRequests"]["totalCount"], "merged": user["merged"]["totalCount"]},
        "issues": {"count": user["issues"]["totalCount"], "open": user["openIssues"]["totalCount"],
                   "closed": user["closedIssues"]["totalCount"]},
        "calendar": summarize(days),
        "fetched_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
    }
    return validate(data)


def shade(color, amount):
    return "#" + "".join(f"{round(int(color[i:i + 2], 16) * amount):02x}" for i in (1, 3, 5))


def isometric(days, palette, x0, y0):
    """Draw one cube per day: weeks run down-right, weekdays down-left."""
    top = max(day["count"] for day in days) or 1
    u, rise = 6.4, 46
    shapes = []
    for i, day in enumerate(days):
        week, d = (i + days[0]["weekday"]) // 7, day["weekday"]
        cx = x0 + 7 * u + (week - d) * u
        cy = y0 + rise + (week + d) * u / 2
        h = 0 if not day["count"] else 3 + (rise - 3) * day["count"] / top
        color = palette[day["level"]]
        top_face = f"M{cx:.1f} {cy - h:.1f}l{u:.1f} {u / 2:.1f}l{-u:.1f} {u / 2:.1f}l{-u:.1f} {-u / 2:.1f}z"
        if h:
            left = f"M{cx - u:.1f} {cy + u / 2 - h:.1f}l{u:.1f} {u / 2:.1f}v{h:.1f}l{-u:.1f} {-u / 2:.1f}z"
            right = f"M{cx + u:.1f} {cy + u / 2 - h:.1f}l{-u:.1f} {u / 2:.1f}v{h:.1f}l{u:.1f} {-u / 2:.1f}z"
            shapes.append(f'<path d="{left}" fill="{shade(color, .82)}"/>')
            shapes.append(f'<path d="{right}" fill="{shade(color, .68)}"/>')
        shapes.append(f'<path d="{top_face}" fill="{color}"/>')
    return "<g>" + "".join(shapes) + "</g>"


def dashboard(data, theme):
    dark = theme == "dark"
    bg, panel, stroke, ink, muted, accent, violet = (
        ("#0d1117", "#151c25", "#2a3543", "#eef5ff", "#93a4b8", "#5eead4", "#c4b5fd")
        if dark else
        ("#ffffff", "#f6f8fb", "#d8e1eb", "#182335", "#64748b", "#087f72", "#7355b4")
    )
    languages = data["languages"]
    ranked = sorted(languages["stats"].items(), key=lambda item: item[1], reverse=True)
    total = sum(value for _, value in ranked)
    prs = data["pr"]
    issues = data["issues"]
    calendar = data["calendar"]
    date = datetime.fromisoformat(data["fetched_at"]).strftime("%Y.%m.%d")
    output = [f'''<svg xmlns="{SVG_NS}" width="800" height="728" viewBox="0 0 800 728" fill="none" role="img" aria-labelledby="title description">
<title id="title">{USER} · GitHub Insights</title>
<desc id="description">GitHub snapshot from {date}. {prs['count']} pull requests, {prs['merged']} merged, {issues['count']} issues. Language shares reflect repository code size. Calendar covers the past year.</desc>
<defs>
  <linearGradient id="header-glow" x1="0" y1="0" x2="800" y2="180" gradientUnits="userSpaceOnUse">
    <stop stop-color="{accent}" stop-opacity="0.10"/><stop offset="0.55" stop-color="{bg}" stop-opacity="0"/><stop offset="1" stop-color="{violet}" stop-opacity="0.07"/>
  </linearGradient>
</defs>
<rect x="0.5" y="0.5" width="799" height="727" rx="22" fill="{bg}" stroke="{stroke}"/>
<path d="M23 1H777Q799 1 799 23V120H1V23Q1 1 23 1Z" fill="url(#header-glow)"/>
<g font-family="Segoe UI, Arial, sans-serif">
<text x="28" y="38" fill="{accent}" font-size="11" font-weight="700" letter-spacing="2.8">GITHUB INSIGHTS</text>
<text x="26" y="86" fill="{ink}" font-size="40" font-weight="700" letter-spacing="-1.6">{USER}<tspan fill="{accent}">.</tspan></text>
<text x="232" y="84" fill="{muted}" font-size="13">Code, contributions &amp; language activity</text>
<rect x="648" y="28" width="124" height="28" rx="14" stroke="{stroke}"/>
<circle cx="665" cy="42" r="3" fill="{accent}"/>
<text x="677" y="46" fill="{muted}" font-size="10" font-weight="600" letter-spacing="1">DAILY</text>''']

    def text(x, y, value, size=14, color=ink, weight="400", extra=""):
        output.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" {extra}>{escape(str(value))}</text>')

    def rect(x, y, width, height, fill=panel, radius=16):
        output.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}"/>')

    stats = [("PULL REQUESTS", prs["count"], "Authored across GitHub", accent),
             ("MERGED", prs["merged"], "Pull requests accepted", violet),
             ("ISSUES", issues["count"], f"{issues['closed']} closed · {issues['open']} open", accent)]
    for i, (label, value, detail, color) in enumerate(stats):
        x = 24 + i * 256
        rect(x, 120, 240, 100)
        text(x + 18, 144, label, 10, muted, "600", 'letter-spacing="1.6"')
        text(x + 17, 183, f"{value:,}", 34, color, "700", 'letter-spacing="-1"')
        text(x + 18, 204, detail, 11, muted)

    rect(24, 236, 448, 430)
    rect(488, 236, 288, 430)
    text(44, 270, "Contribution skyline", 18, ink, "600")
    text(44, 291, "Past 12 months · one column per day", 11, muted)
    palette = (("#233044", "#164c47", "#238b7c", "#3fcbb0", "#8af6d9") if dark
               else ("#e2e8f0", "#bdeee2", "#6fd8bd", "#2ca891", "#087f72"))
    output.append(isometric(calendar["days"], palette, 60, 300))
    colors = dict(zip(palette, palette))
    text(44, 568, "Less", 10, muted)
    for i, color in enumerate(colors.values()):
        rect(73 + 15 * i, 559, 10, 10, color, 3)
    text(155, 568, "More", 10, muted)
    output.append(f'<path d="M44 588H452" stroke="{stroke}"/>')
    for x, value, label in [(44, f"{calendar['streak']['max']} days", "Longest streak"),
                            (188, calendar["average"], "Daily average"),
                            (332, calendar["max"], "Busiest day")]:
        text(x, 625, value, 22, accent, "600")
        text(x, 647, label, 10, muted)

    text(508, 270, "Language mix", 18, ink, "600")
    text(508, 291, "By owned repository code size", 11, muted)
    cx, cy, radius = 632, 371, 58
    length = 2 * math.pi * radius
    output.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" stroke="{stroke}" stroke-width="17"/>')
    offset = 0
    display = ranked[:4] + [("Other", sum(value for _, value in ranked[4:]))]
    display_colors = [languages["colors"].get(name, muted) if name != "Other" else muted for name, _ in display]
    for (name, value), color in zip(display, display_colors):
        share = value / total
        output.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" stroke="{color}" stroke-width="17" stroke-dasharray="{max(0, length * share - 2):.3f} {length:.3f}" stroke-dashoffset="{-offset:.3f}" transform="rotate(-90 {cx} {cy})"/>')
        offset += length * share
    text(cx, cy + 5, len(ranked), 32, ink, "700", 'text-anchor="middle"')
    text(cx, cy + 25, "languages", 11, muted, extra='text-anchor="middle"')
    for i, ((name, value), color) in enumerate(zip(display, display_colors)):
        y = 468 + i * 38
        output.append(f'<circle cx="513" cy="{y - 4}" r="3" fill="{color}"/>')
        text(525, y, name, 12, ink, "500")
        text(756, y, f"{value / total:.1%}", 12, muted, extra='text-anchor="end"')
        rect(508, y + 10, 248, 4, stroke, 2)
        rect(508, y + 10, 248 * value / total, 4, color, 2)

    text(28, 702, "GITHUB INSIGHTS  /  PUBLIC GITHUB DATA", 9, muted, "600", 'letter-spacing="1.2"')
    text(772, 702, f"SNAPSHOT  {date} KST", 9, muted, extra='text-anchor="end" letter-spacing="0.7"')
    output.append("</g></svg>\n")
    result = "\n".join(output)
    ET.fromstring(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--browser-channel", default=None)
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.browser_channel, headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 728}, device_scale_factor=2)
        data = refresh() if args.refresh else validate(json.loads(SNAPSHOT.read_text(encoding="utf-8")))
        # Build both variants before replacing any previously working outputs.
        rendered = {theme: dashboard(data, theme) for theme in ("dark", "light")}
        for theme, source in rendered.items():
            page.set_content(source)
            overflow = page.locator("text").evaluate_all('''nodes => nodes.filter(t => {
                const b = t.getBBox(); return b.x + b.width > 780;
            }).map(t => t.textContent)''')
            assert not overflow, overflow
            png = page.locator("svg").first.screenshot(omit_background=True)
            (ASSETS / f"github-metrics-{theme}.svg").write_text(source, encoding="utf-8")
            (ASSETS / f"github-metrics-{theme}.png").write_bytes(png)
        SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        browser.close()
    print("Rendered both Insights dashboards from a validated snapshot; no text overflow.")


if __name__ == "__main__":
    main()

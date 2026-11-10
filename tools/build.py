#!/usr/bin/env python3
"""Builds the animated SVGs for the profile README (dark + light), matching shaileshmaddikera.github.io.

GitHub shows README images in a sandbox: no scripts and no web fonts. So every SVG embeds the
glyphs it needs (subset fonts from Google Fonts, as base64 woff2) and animates with CSS/SMIL only.

    python3 tools/build.py        # writes assets/*.svg (needs network the first time; fonts are cached)
"""
import base64, hashlib, json, math, os, re, subprocess, urllib.parse
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
CACHE = os.path.join(ROOT, "tools", ".fontcache")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

THEMES = {
    "dark": dict(bg="#0b0b0c", card="#141416", ink="#ededee", ink2="#b4b4ba", muted="#78787f",
                 line="#232326", line2="#323236", accent="#c8f542", accent_text="#c8f542", dot="237,237,238", glow=0.16, logo_bg="#ededee", logo_ink="#0b0b0c"),
    "light": dict(bg="#f6f5f1", card="#ffffff", ink="#111113", ink2="#4a4a50", muted="#85858c",
                  line="#e4e2dc", line2="#d6d4cd", accent="#c8f542", accent_text="#3d6a00", dot="17,17,19", glow=0.35, logo_bg="#111113", logo_ink="#f6f5f1"),
}

# ───────────────────────── Fonts ─────────────────────────

def _curl(url):
    return subprocess.run(["curl", "-sfL", "-A", UA, url], check=True, capture_output=True).stdout

def font_face(family, weight=400, italic=False, text=""):
    """@font-face rule for `family` holding only the glyphs in `text`."""
    chars = "".join(sorted(set(text))) or "a"
    key = hashlib.sha1(f"{family}|{weight}|{italic}|{chars}".encode()).hexdigest()[:16]
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, key + ".woff2")
    if not os.path.exists(path):
        axis = f"ital,wght@1,{weight}" if italic else f"wght@{weight}"
        fam = family.replace(" ", "+")
        spec = f"{fam}:{axis}" if family not in SINGLE_WEIGHT else (f"{fam}:ital@1" if italic else fam)
        css = _curl(f"https://fonts.googleapis.com/css2?family={spec}&text={urllib.parse.quote(chars)}&display=block").decode()
        url = re.search(r"url\((https://[^)]+)\)", css).group(1)
        with open(path, "wb") as f:
            f.write(_curl(url))
    data = base64.b64encode(open(path, "rb").read()).decode()
    style = "italic" if italic else "normal"
    return (f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2');}}")

# Families Google serves without a weight axis.
SINGLE_WEIGHT = {"Bebas Neue", "Monoton", "Pacifico", "Press Start 2P", "Rubik Glitch", "Major Mono Display",
                 "Bungee Shade", "Silkscreen", "Rubik Mono One", "Righteous", "Instrument Serif"}

class Fonts:
    """Collects text per font while an SVG is drawn, then emits subset @font-face rules."""
    def __init__(self):
        self.used = {}
    def use(self, family, weight, italic, text):
        k = (family, weight, italic)
        self.used[k] = self.used.get(k, "") + text
        return text
    def css(self):
        return "".join(font_face(f, w, i, t) for (f, w, i), t in self.used.items())

def T(fonts, x, y, text, family="Geist", weight=400, size=16, fill="#000", italic=False, anchor="start",
      spacing=None, cls=None, upper=False, extra=""):
    shown = text.upper() if upper else text
    fonts.use(family, weight, italic, shown)
    attrs = [f'x="{x}"', f'y="{y}"', f"font-family=\"'{family}'\"", f'font-weight="{weight}"', f'font-size="{size}"', f'fill="{fill}"']
    if italic: attrs.append('font-style="italic"')
    if anchor != "start": attrs.append(f'text-anchor="{anchor}"')
    if spacing is not None: attrs.append(f'letter-spacing="{spacing}"')
    if cls: attrs.append(f'class="{cls}"')
    if extra: attrs.append(extra)
    return f"<text {' '.join(attrs)}>{escape(shown)}</text>"

def tspan_line(fonts, x, y, parts, size, fill, spacing=None):
    """One line made of (text, family, weight, italic, fill_or_None) runs."""
    spans = []
    for text, fam, wt, it, col in parts:
        fonts.use(fam, wt, it, text)
        st = ' font-style="italic"' if it else ""
        spans.append(f"<tspan font-family=\"'{fam}'\" font-weight=\"{wt}\"{st} fill=\"{col or fill}\">{escape(text)}</tspan>")
    ls = f' letter-spacing="{spacing}"' if spacing is not None else ""
    return f'<text x="{x}" y="{y}" font-size="{size}"{ls}>{"".join(spans)}</text>'

def svg(w, h, body, fonts, css="", title=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
            f"<title>{escape(title)}</title><style>{fonts.css()}{css}"
            "@media (prefers-reduced-motion: reduce){*{animation:none!important}}</style>"
            f"{body}</svg>")

def dot_grid(id_, c, gap=26, alpha=0.11):
    return (f'<pattern id="{id_}" width="{gap}" height="{gap}" patternUnits="userSpaceOnUse">'
            f'<circle cx="{gap/2}" cy="{gap/2}" r="1" fill="rgba({c["dot"]},{alpha})"/></pattern>')

def line_grid(id_, c, gap=24):
    return (f'<pattern id="{id_}" width="{gap}" height="{gap}" patternUnits="userSpaceOnUse">'
            f'<path d="M {gap} 0 L 0 0 0 {gap}" fill="none" stroke="{c["line"]}" stroke-width="1"/></pattern>')

def arrow(x, y, s, color):
    """A small ↗ drawn as a path (fonts may not have the glyph)."""
    return (f'<path d="M{x} {y+s} L{x+s} {y} M{x+s*0.3} {y} L{x+s} {y} L{x+s} {y+s*0.7}" fill="none" '
            f'stroke="{color}" stroke-width="{max(1.6, s/7):.1f}" stroke-linecap="round" stroke-linejoin="round"/>')

# ───────────────────────── Header (animated name) ─────────────────────────

FACES = [
    ("Instrument Serif", 400, True, 1.0, False), ("Geist Mono", 400, False, 0.86, False),
    ("Bebas Neue", 400, False, 1.08, False), ("UnifrakturCook", 700, False, 1.0, True),
    ("Pacifico", 400, False, 0.86, False), ("Monoton", 400, False, 0.7, False),
    ("Press Start 2P", 400, False, 0.46, False), ("Syne", 800, False, 0.98, True),
    ("Rubik Glitch", 400, False, 0.84, False), ("Bungee Shade", 400, False, 0.64, False),
    ("Playfair Display", 900, True, 1.0, True), ("Orbitron", 800, False, 0.7, False),
    ("Silkscreen", 400, False, 0.68, False), ("Caveat", 700, False, 1.12, False),
    ("Space Grotesk", 300, False, 0.98, False),
]

def header(theme):
    c = THEMES[theme]; f = Fonts(); W, H = 1280, 640
    n = len(FACES); period = 14.0
    # Slow → fast → slow, like the website intro.
    durs = [0.09 + 0.17 * (1 - math.sin(math.pi * i / (n - 1))) for i in range(n)]
    t, windows = 0.25, []
    for d in durs:
        windows.append((t, t + d)); t += d
    settle = t
    pct = lambda s: f"{100 * s / period:.3f}%"
    fade = 0.05
    css = [".face{opacity:0}.home{opacity:1}"]
    layers = []
    base = 156
    for i, (fam, wt, it, scale, acc) in enumerate(FACES):
        s, e = windows[i]
        css.append(f"@keyframes f{i}{{0%,{pct(max(0, s - fade))}{{opacity:0;transform:translateY(10px)}}"
                   f"{pct(s)},{pct(e)}{{opacity:1;transform:none}}{pct(e + fade)},100%{{opacity:0;transform:translateY(-8px)}}}}"
                   f".f{i}{{animation:f{i} {period}s infinite}}")
        layers.append(T(f, 64, 330, "Shailesh", fam, wt, round(base * scale), c["accent"] if acc else c["ink"], italic=it,
                        cls=f"face f{i}", spacing="-0.02em"))
    css.append(f"@keyframes home{{0%,{pct(settle - 0.02)}{{opacity:0;transform:translateY(14px)}}{pct(settle + 0.35)},{pct(period - 0.35)}{{opacity:1;transform:none}}100%{{opacity:0}}}}"
               f".home{{animation:home {period}s infinite cubic-bezier(.2,.7,.1,1)}}")
    css.append(f"@keyframes bar{{0%{{transform:scaleX(0)}}{pct(settle)}{{transform:scaleX(1)}}{pct(period - 0.4)}{{transform:scaleX(1);opacity:1}}100%{{transform:scaleX(1);opacity:0}}}}"
               f".bar{{transform-origin:64px 0;animation:bar {period}s infinite}}")
    css.append("@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}.pulse{animation:pulse 2.2s infinite}")
    css.append(".face,.home{transform-box:fill-box}")
    body = f"""
<defs>{dot_grid('d', c)}<radialGradient id="g" cx="0.78" cy="0.25" r="0.6"><stop offset="0" stop-color="{c['accent']}" stop-opacity="{c['glow']}"/><stop offset="1" stop-color="{c['accent']}" stop-opacity="0"/></radialGradient>
<clipPath id="r"><rect width="{W}" height="{H}" rx="28"/></clipPath></defs>
<g clip-path="url(#r)"><rect width="{W}" height="{H}" fill="{c['bg']}"/><rect width="{W}" height="{H}" fill="url(#d)"/><rect width="{W}" height="{H}" fill="url(#g)"/></g>
<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="28" fill="none" stroke="{c['line']}"/>
<rect x="64" y="52" width="52" height="52" rx="14" fill="{c['logo_bg']}"/>
{T(f, 90, 86, "SM", "Geist", 700, 19, c['logo_ink'], anchor="middle", spacing="-0.02em")}
{T(f, W-64, 84, "shaileshmaddikera.github.io", "Geist Mono", 400, 17, c['muted'], anchor="end")}
<circle cx="70" cy="174" r="6" fill="{c['accent']}" class="pulse"/>
{T(f, 88, 180, "Building in stealth", "Geist Mono", 400, 17, c['ink2'], upper=True, spacing="0.06em")}
{''.join(layers)}
{T(f, 64, 330, "Shailesh", "Geist", 600, base, c['ink'], cls="home", spacing="-0.045em")}
{T(f, 64, 478, "Maddikera", "Geist", 600, base, c['muted'], spacing="-0.045em")}
{tspan_line(f, 64, 566, [("Student & builder — ", "Geist", 400, False, None), ("AI agents", "Instrument Serif", 400, True, c['accent_text']), (", native apps, full-stack systems.", "Geist", 400, False, None)], 30, c['ink2'], spacing="-0.01em")}
<rect x="64" y="598" width="{W-128}" height="2" rx="1" fill="{c['line']}"/>
<rect x="64" y="598" width="{W-128}" height="2" rx="1" fill="{c['accent']}" class="bar"/>
"""
    return svg(W, H, body, f, "".join(css), "Shailesh Maddikera — Student & builder. AI agents, native apps, full-stack systems. Building in stealth.")

# ───────────────────────── Pills ─────────────────────────

def pill(theme, label, width):
    c = THEMES[theme]; f = Fonts(); W, H = width, 56
    body = f"""<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="{(H-2)/2}" fill="{c['card']}" stroke="{c['line2']}"/>
{T(f, 26, 35, label, "Geist", 500, 19, c['ink'], spacing="-0.01em")}
{arrow(W-40, 21, 13, c['ink'])}"""
    return svg(W, H, body, f, "", label)

# ───────────────────────── Section labels ─────────────────────────

def label(theme, num, text, title_parts):
    c = THEMES[theme]; f = Fonts(); W, H = 1280, 150
    parts = [(t, "Instrument Serif" if it else "Geist", 400 if it else 500, it, c['accent_text'] if it else None) for t, it in title_parts]
    body = f"""{T(f, 0, 30, f"{num} — {text}", "Geist Mono", 400, 18, c['muted'], upper=True, spacing="0.05em")}
{tspan_line(f, 0, 112, parts, 72, c['ink'], spacing="-0.04em")}"""
    return svg(W, H, body, f, "", f"{text}")

# ───────────────────────── Project cards ─────────────────────────

def art_surety(c, f):
    bars = [(150, 34, 140), (150, 52, 110), (150, 70, 128), (150, 88, 96), (150, 106, 134), (150, 124, 104)]
    rects = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="7" rx="3.5" fill="{c["line2"]}"/>' for x, y, w in bars)
    return f"""<g transform="translate(150,14) scale(1.05)">{rects}
<rect class="cite" x="146" y="30" width="148" height="15" rx="4" fill="none" stroke="{c['accent_text']}" stroke-width="1.6"/>
<circle cx="62" cy="68" r="26" fill="{c['card']}" stroke="{c['ink']}" stroke-width="1.5"/>
<circle cx="96" cy="112" r="26" fill="{c['card']}" stroke="{c['accent_text']}" stroke-width="1.5"/>
{T(f, 62, 75, "G", "Geist", 600, 20, c['ink'], anchor="middle")}
{T(f, 96, 119, "C", "Geist", 600, 20, c['ink'], anchor="middle")}
<circle r="4" fill="{c['accent_text']}"><animateMotion dur="2.4s" repeatCount="indefinite" path="M62 68 Q 40 110 96 112 Q 118 70 62 68"/></circle>
</g>""", ("@keyframes cite{0%,12%{transform:translateY(0)}20%,37%{transform:translateY(36px)}45%,62%{transform:translateY(72px)}70%,87%{transform:translateY(18px)}95%,100%{transform:translateY(0)}}"
          ".cite{animation:cite 6s cubic-bezier(.76,0,.24,1) infinite}")

def art_dna(c, f=None):
    out, css = [], ["@keyframes s{from{transform:translateY(0) scale(.7)}to{transform:translateY(126px) scale(1.15)}}",
                    "@keyframes b{from{transform:scaleY(1)}to{transform:scaleY(.05)}}",
                    ".a,.b2,.br{transform-box:fill-box;transform-origin:center}"]
    for i in range(16):
        x = 200 + i * 16; d = -i * 0.22
        out.append(f'<rect class="br" x="{x-1}" y="44" width="2" height="122" fill="{c["line2"]}" style="animation:b 1.3s ease-in-out {d}s infinite alternate"/>')
        out.append(f'<circle class="a" cx="{x}" cy="40" r="4.5" fill="{c["ink"]}" style="animation:s 2.6s ease-in-out {d}s infinite alternate"/>')
        out.append(f'<circle class="b2" cx="{x}" cy="40" r="4.5" fill="{c["accent_text"]}" style="animation:s 2.6s ease-in-out {d}s infinite alternate-reverse"/>')
    return "".join(out), "".join(css)

def art_rl(c, f=None):
    path = "M-10 170 C 120 170, 140 60, 300 60 S 520 140, 660 40"
    rays = "".join(f'<line x1="0" y1="0" x2="{x}" y2="{y}"/>' for x, y in [(80, -52), (94, -20), (98, 8), (86, 38), (62, 64)])
    return f"""<path d="{path}" fill="none" stroke="{c['line2']}" stroke-width="30" stroke-linecap="round"/>
<path d="{path}" fill="none" stroke="{c['card']}" stroke-width="25" stroke-linecap="round"/>
<g><g class="rays" stroke="{c['accent_text']}" stroke-width="1.2" stroke-dasharray="2 3">{rays}</g>
<path d="M-12 -7 L 14 0 L -12 7 Z" fill="{c['ink']}"/>
<animateMotion dur="5s" repeatCount="indefinite" rotate="auto" path="{path}"/></g>""", \
        "@keyframes r{from{opacity:.25}to{opacity:.95}}.rays{animation:r 1.2s ease-in-out infinite alternate}"

def art_stealth(c, f=None):
    widths = [0.82, 0.64, 0.9, 0.48, 0.72]
    bars, sweep = [], []
    for i, w in enumerate(widths):
        y = 50 + i * 24; wpx = 360 * w
        bars.append(f'<rect x="140" y="{y}" width="{wpx:.0f}" height="13" rx="3" fill="{c["ink"]}" opacity=".88"/>')
        sweep.append(f'<rect x="140" y="{y}" width="{wpx:.0f}" height="13" rx="3"/>')
    return f"""<defs><clipPath id="rb">{''.join(sweep)}</clipPath>
<linearGradient id="sw" x1="0" x2="1"><stop offset="0" stop-color="#c8f542" stop-opacity="0"/><stop offset=".5" stop-color="#c8f542" stop-opacity=".6"/><stop offset="1" stop-color="#c8f542" stop-opacity="0"/></linearGradient></defs>
{''.join(bars)}<g clip-path="url(#rb)"><rect class="sweep" x="0" y="40" width="160" height="130" fill="url(#sw)"/></g>""", \
        "@keyframes sweep{from{transform:translateX(0)}to{transform:translateX(520px)}}.sweep{animation:sweep 2.8s cubic-bezier(.76,0,.24,1) infinite}"

PROJECTS = [
    dict(id="surety", art=art_surety, year="2026", kind="Personal · AI systems", title="Surety.ai",
         desc=["A Generator proposes; a Checker challenges it with cited", "policy clauses. Every answer leaves an audit record."],
         link="View on GitHub", href="https://github.com/ShaileshMaddikera/Surety.ai"),
    dict(id="dna", art=art_dna, year="2025", kind="Personal · Health", title="MyGeneticMenu",
         desc=["Personalized diet plans from your genetics, powered by", "an interpretation engine and Gemini."],
         link="View on GitHub", href="https://github.com/ShaileshMaddikera/MyGeneticMenu"),
    dict(id="rl", art=art_rl, year="2025", kind="Team of 4 · Deep RL", title="Trackmania RL driver",
         desc=["Soft Actor-Critic in PyTorch, learning to drive from", "LIDAR-style distances and car telemetry."],
         link="Team project · code not public", href=None),
    dict(id="stealth", art=art_stealth, year="Now", kind="Stealth", title="Stealth build",
         desc=["Something new across apps, cloud and hardware.", "Details soon."],
         link="Coming soon", href=None),
]

def card(theme, p):
    c = THEMES[theme]; f = Fonts(); W, H = 640, 440; AH = 210
    art, art_css = p["art"](c, f)
    stamp = ""
    if p["id"] == "stealth":
        stamp = (f'<g transform="translate({W-150},{AH-44}) rotate(-6)"><rect width="118" height="30" rx="6" fill="none" stroke="{c["accent_text"]}" stroke-width="1.6"/>'
                 + T(f, 59, 20, "Classified", "Geist Mono", 400, 14, c["accent_text"], anchor="middle", upper=True, spacing="0.06em") + "</g>")
    link_color = c["ink"] if p["href"] else c["muted"]
    link = T(f, 32, 408, p["link"], "Geist", 500, 18, link_color)
    if p["href"]:
        link += arrow(32 + len(p["link"]) * 9.1 + 8, 396, 10, c["ink"])
    body = f"""<defs>{line_grid('lg', c)}<clipPath id="cc"><rect width="{W}" height="{H}" rx="24"/></clipPath><clipPath id="ac"><rect width="{W}" height="{AH}"/></clipPath></defs>
<g clip-path="url(#cc)"><rect width="{W}" height="{H}" fill="{c['card']}"/>
<g clip-path="url(#ac)"><rect width="{W}" height="{AH}" fill="{c['bg'] if p['id']=='stealth' else c['card']}"/><rect width="{W}" height="{AH}" fill="url(#lg)" opacity="{0 if p['id']=='stealth' else 1}"/>{art}{stamp}</g>
<rect y="{AH}" width="{W}" height="1" fill="{c['line']}"/></g>
<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="24" fill="none" stroke="{c['line']}"/>
{T(f, 32, 254, p['year'], "Geist Mono", 400, 16, c['muted'], upper=True, spacing="0.04em")}
{T(f, W-32, 254, p['kind'], "Geist Mono", 400, 16, c['muted'], anchor="end", upper=True, spacing="0.04em")}
{T(f, 32, 300, p['title'], "Geist", 600, 36, c['ink'], spacing="-0.035em")}
{T(f, 32, 338, p['desc'][0], "Geist", 400, 20, c['ink2'])}
{T(f, 32, 366, p['desc'][1], "Geist", 400, 20, c['ink2'])}
{link}"""
    return svg(W, H, body, f, art_css, f"{p['title']} — {' '.join(p['desc'])}")

# ───────────────────────── Journey ─────────────────────────

JOURNEY = [
    ("Now", "Stealth build", "An AI product across apps, cloud and hardware. More soon.", "Stealth"),
    ("Nov 2026", "This website", "Hand-built with plain HTML, CSS and JavaScript. No frameworks.", "Personal"),
    ("Aug 2026", "Surety.ai", "Generator vs. Checker, server-validated citations, full audit record.", "AI systems"),
    ("Jun 2025", "MyGeneticMenu", "Genetic data into personalized diet plans with Gemini.", "Health · AI"),
    ("Mar 2025", "Trackmania RL driver", "Soft Actor-Critic in PyTorch, driving from LIDAR and telemetry.", "Deep RL"),
]

def journey(theme):
    c = THEMES[theme]; f = Fonts(); W = 1280; row = 112; top = 10; H = top + row * len(JOURNEY) + 10
    rows = [f'<rect x="0" y="{top}" width="{W}" height="1" fill="{c["line"]}"/>']
    css = "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}.pulse{animation:pulse 2.2s infinite}"
    for i, (when, title, desc, kind) in enumerate(JOURNEY):
        y = top + i * row
        now = i == 0
        if now:
            rows.append(f'<circle cx="6" cy="{y+46}" r="5" fill="{c["accent"]}" class="pulse"/>')
        rows.append(T(f, 22 if now else 0, y + 52, when, "Geist Mono", 400, 17, c['accent_text'] if now else c['muted'], upper=True, spacing="0.04em"))
        rows.append(T(f, 200, y + 52, title, "Geist", 500, 34, c['ink'], spacing="-0.03em"))
        rows.append(T(f, 200, y + 88, desc, "Geist", 400, 21, c['ink2']))
        rows.append(T(f, W, y + 51, kind, "Geist Mono", 400, 16, c['muted'], anchor="end", upper=True, spacing="0.04em"))
        rows.append(f'<rect x="0" y="{y+row}" width="{W}" height="1" fill="{c["line"]}"/>')
    return svg(W, H, "".join(rows), f, css, "Journey: " + "; ".join(f"{w} {t}" for w, t, _, _ in JOURNEY))

# ───────────────────────── Focus ─────────────────────────

FOCUS = [
    ("01", "AI agents & LLM systems", ["Multi-model systems that check each other’s work,", "real-time voice and vision agents, grounded answers."], "Gemini · LiveKit · FastAPI · PyTorch"),
    ("02", "Native Apple apps", ["Swift 6 and SwiftUI for iPhone, iPad and Mac, with", "on-device Vision and Apple Intelligence, fully tested."], "Swift 6 · SwiftUI · Vision · XCTest"),
    ("03", "Full-stack & infrastructure", ["TypeScript and Python backends, edge databases, data", "pipelines and end-to-end tests that run in production."], "Next.js · TypeScript · Turso · Vercel"),
    ("04", "Hardware & wearables", ["On-device perception and early work on taking AI", "off the phone and onto purpose-built hardware."], "On-device ML · Computer vision · Real-time media"),
]

def focus(theme):
    c = THEMES[theme]; f = Fonts(); W = 1280; cw, ch, gap = 632, 250, 16; H = ch * 2 + gap
    out = []
    for i, (n, title, desc, tags) in enumerate(FOCUS):
        x = (i % 2) * (cw + gap); y = (i // 2) * (ch + gap)
        out.append(f'<rect x="{x+0.5}" y="{y+0.5}" width="{cw-1}" height="{ch-1}" rx="22" fill="{c["card"]}" stroke="{c["line"]}"/>')
        out.append(T(f, x + 28, y + 46, n, "Geist Mono", 400, 17, c['accent_text']))
        out.append(T(f, x + 28, y + 94, title, "Geist", 600, 32, c['ink'], spacing="-0.035em"))
        out.append(T(f, x + 28, y + 134, desc[0], "Geist", 400, 20, c['ink2']))
        out.append(T(f, x + 28, y + 162, desc[1], "Geist", 400, 20, c['ink2']))
        out.append(T(f, x + 28, y + 218, tags, "Geist Mono", 400, 15, c['muted'], upper=True, spacing="0.05em"))
    return svg(W, H, "".join(out), f, "", "What I work on: " + "; ".join(t for _, t, _, _ in FOCUS))

# ───────────────────────── Footer ─────────────────────────

def footer(theme):
    c = THEMES[theme]; f = Fonts(); W, H = 1280, 200
    line = tspan_line(f, 0, 84, [("I like turning ", "Geist", 500, False, None), ("ideas", "Instrument Serif", 400, True, c['accent_text']),
                                 (" into things people actually ", "Geist", 500, False, None), ("use", "Instrument Serif", 400, True, c['accent_text']),
                                 (".", "Geist", 500, False, None)], 52, c['ink'], spacing="-0.035em")
    body = f"""{line}
<rect x="0" y="140" width="{W}" height="1" fill="{c['line']}"/>
{T(f, 0, 182, "© 2026 Shailesh Maddikera", "Geist Mono", 400, 17, c['muted'], upper=True, spacing="0.05em")}
{T(f, W, 182, "Designed & built by hand", "Geist Mono", 400, 17, c['muted'], anchor="end", upper=True, spacing="0.05em")}"""
    return svg(W, H, body, f, "", "I like turning ideas into things people actually use.")

# ───────────────────────── Build ─────────────────────────

def main():
    os.makedirs(OUT, exist_ok=True)
    files = {}
    for th in THEMES:
        files[f"header-{th}.svg"] = header(th)
        for name, w in [("website", 176), ("linkedin", 176), ("resume", 164)]:
            files[f"pill-{name}-{th}.svg"] = pill(th, {"website": "Website", "linkedin": "LinkedIn", "resume": "Résumé"}[name], w)
        files[f"label-work-{th}.svg"] = label(th, "01", "Selected work", [("Things I’ve ", False), ("built", True), (".", False)])
        files[f"label-journey-{th}.svg"] = label(th, "02", "Journey", [("The road ", False), ("so far", True), (".", False)])
        files[f"label-focus-{th}.svg"] = label(th, "03", "What I work on", [("Where I spend my ", False), ("time", True), (".", False)])
        for p in PROJECTS:
            files[f"card-{p['id']}-{th}.svg"] = card(th, p)
        files[f"journey-{th}.svg"] = journey(th)
        files[f"focus-{th}.svg"] = focus(th)
        files[f"footer-{th}.svg"] = footer(th)
    total = 0
    for name, data in files.items():
        with open(os.path.join(OUT, name), "w") as fh:
            fh.write(data)
        total += len(data.encode())
    print(f"{len(files)} SVGs, {total/1024:.0f} KB total")

if __name__ == "__main__":
    main()

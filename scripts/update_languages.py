
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import requests

USER = os.getenv("GITHUB_USERNAME", "Wesleybarroso")
TOKEN = os.getenv("GITHUB_TOKEN")
OUT = Path("assets/languages-month.svg")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

EXTENSIONS = {
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript",
    ".go": "Go", ".py": "Python",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".rs": "Rust", ".php": "PHP", ".rb": "Ruby",
    ".cs": "C#", ".cpp": "C++", ".cc": "C++",
    ".c": "C", ".h": "C/C++", ".hpp": "C++",
    ".swift": "Swift", ".dart": "Dart",
    ".vue": "Vue", ".svelte": "Svelte",
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sass": "SCSS",
    ".less": "Less", ".sql": "SQL",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
}

COLORS = [
    "#00E5FF", "#1683FF", "#5B63FF", "#8B5CF6",
    "#22C55E", "#F59E0B", "#EF4444", "#EC4899",
]


def api(url, params=None):
    for attempt in range(5):
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code in (404, 409):
            print(f"SKIP {response.status_code}: {url}")
            return None

        if response.status_code in (403, 429):
            retry_after = response.headers.get("Retry-After")
            wait = (
                int(retry_after)
                if retry_after and retry_after.isdigit()
                else min(2 ** attempt, 30)
            )
            print(f"Rate limit. Waiting {wait}s...")
            time.sleep(wait)
            continue

        raise RuntimeError(
            f"GitHub API {response.status_code}: "
            f"{response.text[:500]}"
        )

    raise RuntimeError("GitHub API retry limit reached.")


def pages(url, params=None):
    page = 1

    while True:
        current = dict(params or {})
        current.update({
            "per_page": 100,
            "page": page,
        })

        data = api(url, current)

        if not data:
            return

        yield from data

        if len(data) < 100:
            return

        page += 1


def esc(value):
    return escape(str(value))


def build_donut(ranked, total):
    cx = 295
    cy = 350
    radius = 132
    circumference = 2 * 3.141592653589793 * radius
    offset = 0.0
    parts = []

    for index, (_, value) in enumerate(ranked):
        percentage = value / total * 100.0
        dash = circumference * percentage / 100.0
        color = COLORS[index % len(COLORS)]

        parts.append(
            f"""<circle cx="{cx}" cy="{cy}" r="{radius}"
fill="none" stroke="{color}" stroke-width="36" stroke-linecap="butt"
stroke-dasharray="{dash:.2f} {circumference - dash:.2f}"
stroke-dashoffset="-{offset:.2f}"
transform="rotate(-90 {cx} {cy})"/>"""
        )

        offset += dash

    return "".join(parts)


def build_legend(ranked, total):
    parts = []
    y = 190

    for index, (language, value) in enumerate(ranked):
        percentage = value / total * 100.0
        color = COLORS[index % len(COLORS)]
        bar_width = 496 * percentage / 100.0

        parts.append(
            f"""<g>
<circle cx="547" cy="{y - 5}" r="5" fill="{color}"/>
<text x="565" y="{y}" fill="#E6EDF5"
font-family="Arial" font-size="14" font-weight="700">{esc(language)}</text>
<text x="1060" y="{y}" text-anchor="end" fill="#F7FBFF"
font-family="monospace" font-size="14" font-weight="800">{percentage:.1f}%</text>
<rect x="565" y="{y + 14}" width="496" height="9" rx="4.5" fill="#0C2440"/>
<rect x="565" y="{y + 14}" width="{bar_width:.2f}" height="9" rx="4.5" fill="{color}"/>
</g>"""
        )

        y += 55

    return "".join(parts)


def main():
    now = datetime.now(timezone.utc)
    month_start = datetime(
        now.year,
        now.month,
        1,
        tzinfo=timezone.utc,
    )

    since = month_start.isoformat().replace("+00:00", "Z")
    until = now.isoformat().replace("+00:00", "Z")
    month_label = month_start.strftime("%m/%Y")

    totals = defaultdict(int)

    commits_count = 0
    repos_analyzed = 0
    repos_with_activity = 0
    changed_lines = 0

    repos = pages(
        f"https://api.github.com/users/{USER}/repos",
        {
            "type": "owner",
            "sort": "updated",
            "direction": "desc",
        },
    )

    for repo in repos:
        if repo.get("fork"):
            continue

        repos_analyzed += 1

        full_name = repo["full_name"]
        commits_url = f"https://api.github.com/repos/{full_name}/commits"
        had_activity = False

        for commit in pages(
            commits_url,
            {
                "author": USER,
                "since": since,
                "until": until,
            },
        ):
            had_activity = True

            sha = commit.get("sha")
            if not sha:
                continue

            detail = api(f"{commits_url}/{sha}")
            if not detail:
                continue

            commits_count += 1

            for file in detail.get("files", []):
                filename = file.get("filename", "")
                extension = Path(filename.lower()).suffix
                language = EXTENSIONS.get(extension)

                if not language:
                    continue

                additions = int(file.get("additions", 0))
                deletions = int(file.get("deletions", 0))
                changed = additions + deletions

                totals[language] += changed
                changed_lines += changed

        if had_activity:
            repos_with_activity += 1

    ranked = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:8]

    total = sum(value for _, value in ranked)

    if total and ranked:
        donut = build_donut(ranked, total)
        legend = build_legend(ranked, total)

        top_language = esc(ranked[0][0])
        top_percentage = ranked[0][1] / total * 100.0

        body = f"""<g>
<circle cx="295" cy="350" r="177" fill="#07111D" stroke="#17324D"/>
<circle cx="295" cy="350" r="132" fill="none" stroke="#0C223B" stroke-width="36"/>
{donut}
<circle cx="295" cy="350" r="95" fill="#050C15" stroke="#17344F"/>
<text x="295" y="335" text-anchor="middle" fill="#57E1FF"
font-family="monospace" font-size="10" font-weight="700">TOP LANGUAGE</text>
<text x="295" y="370" text-anchor="middle" fill="#F4F8FC"
font-family="Arial" font-size="25" font-weight="800">{top_language}</text>
<text x="295" y="397" text-anchor="middle" fill="#71869F"
font-family="Arial" font-size="11">{top_percentage:.1f}%</text>
</g>

<g>
<text x="535" y="184" fill="#57DFFF" font-family="Arial"
font-size="11" font-weight="700" letter-spacing="3">
RANKING / PARTICIPAÇÃO
</text>
<text x="535" y="209" fill="#8EA2B9" font-family="Arial" font-size="13">
Percentual da atividade por linguagem
</text>
{legend}
</g>"""
    else:
        body = """<circle cx="295" cy="350" r="177" fill="#07111D" stroke="#17324D"/>
<circle cx="295" cy="350" r="132" fill="none" stroke="#0C223B" stroke-width="36"/>
<circle cx="295" cy="350" r="95" fill="#050C15" stroke="#17344F"/>
<text x="295" y="345" text-anchor="middle" fill="#57E1FF"
font-family="monospace" font-size="10">NO ACTIVITY</text>
<text x="295" y="371" text-anchor="middle" fill="#71869F"
font-family="Arial" font-size="11">Nenhuma atividade no mês</text>
"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
width="1200" height="700" viewBox="0 0 1200 700">

<defs>

<linearGradient id="bg" x1="0" y1="0" x2="1200" y2="700"
gradientUnits="userSpaceOnUse">
<stop stop-color="#05080F"/>
<stop offset=".52" stop-color="#091421"/>
<stop offset="1" stop-color="#04070C"/>
</linearGradient>

<linearGradient id="accent" x1="0" y1="0" x2="1200" y2="0">
<stop stop-color="#00E5FF"/>
<stop offset=".5" stop-color="#1683FF"/>
<stop offset="1" stop-color="#5D63FF"/>
</linearGradient>

<pattern id="grid" width="34" height="34"
patternUnits="userSpaceOnUse">
<path d="M34 0H0V34"
stroke="#5CA8FF"
stroke-opacity=".022"/>
</pattern>

</defs>

<rect width="1200" height="700" rx="26"
fill="url(#bg)"/>

<rect width="1200" height="700" rx="26"
fill="url(#grid)"/>

<path d="M28 70V28H70
M1130 28H1172V70
M28 630V672H70
M1130 672H1172V630"
fill="none"
stroke="url(#accent)"
stroke-width="1.7"/>

<text x="54" y="56"
fill="#57DFFF"
font-family="Arial"
font-size="11"
font-weight="700"
letter-spacing="3">
ALTIXDEV / DEVELOPMENT PULSE
</text>

<text x="54" y="103"
fill="#F4F8FC"
font-family="Arial"
font-size="31"
font-weight="800">
LINGUAGENS MAIS USADAS NO MÊS
</text>

<text x="54" y="130"
fill="#8EA2B9"
font-family="Arial"
font-size="13">
Participação percentual da sua atividade de código • {month_label}
</text>

<text x="1146" y="56"
fill="#57E1FF"
font-family="monospace"
font-size="10"
font-weight="700"
text-anchor="end">
LIVE / MONTHLY
</text>

{body}

<rect x="540" y="492"
width="520" height="82"
rx="18"
fill="#07111D"
stroke="#18344F"/>

<text x="566" y="520"
fill="#57E1FF"
font-family="monospace"
font-size="10"
font-weight="700">
MÉTRICA
</text>

<text x="566" y="545"
fill="#E6EDF5"
font-family="Arial"
font-size="12"
font-weight="700">
Linhas adicionadas + removidas nos commits do mês
</text>

<text x="566" y="563"
fill="#71869F"
font-family="Arial"
font-size="10">
{commits_count} commits • {repos_with_activity} repositórios com atividade • {repos_analyzed} analisados
</text>

<text x="54" y="620"
fill="#71869F"
font-family="Arial"
font-size="10">
{changed_lines} linhas alteradas • ranking por participação percentual
</text>

<text x="1146" y="620"
fill="#57E1FF"
font-family="monospace"
font-size="10"
font-weight="700"
text-anchor="end">
GITHUB ACTIONS
</text>

<line x1="54" y1="635"
x2="1146" y2="635"
stroke="#17334F"/>

<text x="54" y="657"
fill="#71869F"
font-family="Arial"
font-size="10">
Atualizado automaticamente pelo workflow.
</text>

</svg>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")

    print("========================================")
    print("Development Pulse atualizado")
    print("========================================")
    print("Mês:", month_label)
    print("Commits:", commits_count)
    print("Repositórios:", repos_analyzed)
    print("Com atividade:", repos_with_activity)
    print("Linhas alteradas:", changed_lines)
    print("========================================")

    for language, value in ranked:
        percentage = (
            value / total * 100.0
            if total
            else 0.0
        )
        print(f"{language}: {percentage:.1f}%")


if __name__ == "__main__":
    main()

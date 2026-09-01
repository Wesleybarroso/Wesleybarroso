import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

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
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".py": "Python",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".hpp": "C++",
    ".swift": "Swift",
    ".dart": "Dart",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".less": "Less",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
}


ICONS = {
    "TypeScript": "TS",
    "JavaScript": "JS",
    "Go": "GO",
    "Python": "PY",
    "Java": "JV",
    "Kotlin": "KT",
    "Rust": "RS",
    "PHP": "PHP",
    "Ruby": "RB",
    "C#": "C#",
    "C++": "C++",
    "C": "C",
    "C/C++": "C",
    "Swift": "SW",
    "Dart": "DA",
    "Vue": "VU",
    "Svelte": "SV",
    "HTML": "HT",
    "CSS": "CS",
    "SCSS": "SC",
    "Less": "LE",
    "SQL": "DB",
    "Shell": "SH",
}


def api(url, params=None):

    for attempt in range(5):

        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code in (403, 429):

            retry = response.headers.get("Retry-After")

            wait = (
                int(retry)
                if retry and retry.isdigit()
                else min(2 ** attempt, 30)
            )

            time.sleep(wait)

            continue

        if response.status_code == 404:
            return None

        raise RuntimeError(
            f"GitHub API {response.status_code}: "
            f"{response.text[:300]}"
        )

    raise RuntimeError(
        "GitHub API: limite de tentativas atingido."
    )


def pages(url, params=None):

    page = 1

    while True:

        current = dict(params or {})

        current.update({
            "per_page": 100,
            "page": page
        })

        data = api(url, current) or []

        if not data:
            return

        yield from data

        if len(data) < 100:
            return

        page += 1


def escape(value):

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main():

    now = datetime.now(timezone.utc)

    start = datetime(
        now.year,
        now.month,
        1,
        tzinfo=timezone.utc
    )

    since = start.isoformat().replace(
        "+00:00",
        "Z"
    )

    until = now.isoformat().replace(
        "+00:00",
        "Z"
    )

    totals = defaultdict(int)

    commits = 0
    repositories = 0

    repos = pages(
        f"https://api.github.com/users/{USER}/repos",
        {
            "type": "owner",
            "sort": "updated",
            "direction": "desc"
        }
    )

    for repo in repos:

        if repo.get("fork"):
            continue

        repositories += 1

        full_name = repo["full_name"]

        commits_url = (
            f"https://api.github.com/repos/"
            f"{full_name}/commits"
        )

        for commit in pages(
            commits_url,
            {
                "author": USER,
                "since": since,
                "until": until
            }
        ):

            sha = commit.get("sha")

            if not sha:
                continue

            detail = api(
                f"{commits_url}/{sha}"
            )

            if not detail:
                continue

            commits += 1

            for file in detail.get("files", []):

                filename = file.get(
                    "filename",
                    ""
                )

                extension = Path(
                    filename.lower()
                ).suffix

                language = EXTENSIONS.get(
                    extension
                )

                if not language:
                    continue

                changed = (
                    int(file.get("additions", 0))
                    +
                    int(file.get("deletions", 0))
                )

                totals[language] += changed

    ranked = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True
    )[:8]

    total = sum(
        value
        for _, value in ranked
    )

    month = start.strftime("%m/%Y")

    if total == 0:

        rows = """
        <text x="54" y="205"
              fill="#CBD5E1"
              font-family="Arial"
              font-size="16">
            Nenhuma atividade de código detectada neste mês.
        </text>

        <text x="54" y="232"
              fill="#64748B"
              font-family="Arial"
              font-size="12">
            O gráfico será preenchido automaticamente quando houver commits.
        </text>
        """

    else:

        rows = ""

        y = 185

        for name, value in ranked:

            percentage = (
                value / total
            ) * 100

            width = max(
                8,
                820 * percentage / 100
            )

            icon = ICONS.get(
                name,
                "++"
            )

            rows += f"""
            <g>

              <circle
                cx="40"
                cy="{y + 14}"
                r="13"
                fill="#061A37"
                stroke="#1683FF"
                stroke-opacity=".7"
              />

              <text
                x="40"
                y="{y + 18}"
                text-anchor="middle"
                fill="#7DD3FC"
                font-family="monospace"
                font-size="8"
                font-weight="700"
              >
                {escape(icon)}
              </text>

              <text
                x="62"
                y="{y + 4}"
                fill="#E2E8F0"
                font-family="Arial"
                font-size="14"
                font-weight="700"
              >
                {escape(name)}
              </text>

              <rect
                x="62"
                y="{y + 15}"
                width="820"
                height="16"
                rx="8"
                fill="#0B2346"
              />

              <rect
                x="62"
                y="{y + 15}"
                width="{width:.2f}"
                height="16"
                rx="8"
                fill="url(#line)"
                filter="url(#glow)"
              />

              <text
                x="910"
                y="{y + 29}"
                fill="#00D9FF"
                font-family="monospace"
                font-size="14"
                text-anchor="end"
              >
                {percentage:.1f}%
              </text>

            </g>
            """

            y += 52

    svg = f"""<svg
xmlns="http://www.w3.org/2000/svg"
width="1200"
height="620"
viewBox="0 0 1200 620">

<defs>

<linearGradient
id="bg"
x1="0"
y1="0"
x2="1"
y2="1">

<stop
stop-color="#020617"/>

<stop
offset=".55"
stop-color="#071A38"/>

<stop
offset="1"
stop-color="#020617"/>

</linearGradient>


<linearGradient
id="line"
x1="0"
y1="0"
x2="1"
y2="0">

<stop
stop-color="#00D9FF"/>

<stop
offset=".5"
stop-color="#1683FF"/>

<stop
offset="1"
stop-color="#0066FF"/>

</linearGradient>


<filter id="glow">

<feGaussianBlur
stdDeviation="4"
result="b"/>

<feMerge>

<feMergeNode
in="b"/>

<feMergeNode
in="SourceGraphic"/>

</feMerge>

</filter>


<pattern
id="grid"
width="32"
height="32"
patternUnits="userSpaceOnUse">

<path
d="M32 0H0V32"
stroke="#1683FF"
stroke-opacity=".08"/>

</pattern>

</defs>


<rect
width="1200"
height="620"
rx="22"
fill="url(#bg)"/>


<rect
width="1200"
height="620"
rx="22"
fill="url(#grid)"/>


<path
d="M25 70V25H70
M1130 25H1175V70
M25 550V595H70
M1130 595H1175V550"
stroke="url(#line)"
stroke-width="2"/>


<text
x="54"
y="58"
fill="#7DD3FC"
font-family="Arial"
font-size="13"
letter-spacing="3">

ALTIXDEV • DEVELOPMENT PULSE

</text>


<text
x="54"
y="105"
fill="#FFFFFF"
font-family="Arial"
font-size="31"
font-weight="800">

LINGUAGENS EM MOVIMENTO

</text>


<text
x="54"
y="132"
fill="#64748B"
font-family="Arial"
font-size="13">

Atividade de desenvolvimento • {month}

</text>


<text
x="1146"
y="105"
fill="#00D9FF"
font-family="monospace"
font-size="13"
text-anchor="end">

AUTO / LIVE

</text>


{rows}


<line
x1="54"
y1="560"
x2="1146"
y2="560"
stroke="#1683FF"
stroke-opacity=".25"/>


<text
x="54"
y="586"
fill="#64748B"
font-family="Arial"
font-size="11">

{commits} commits • {repositories} repositórios analisados

</text>


<text
x="1146"
y="586"
fill="#00D9FF"
font-family="monospace"
font-size="10"
text-anchor="end">

GITHUB ACTIONS

</text>

</svg>
"""

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUT.write_text(
        svg,
        encoding="utf-8"
    )

    print(
        "Development Pulse atualizado."
    )

    print(
        "Repositórios:",
        repositories
    )

    print(
        "Commits:",
        commits
    )

    print(
        "Ranking:",
        ranked
    )


if __name__ == "__main__":
    main()

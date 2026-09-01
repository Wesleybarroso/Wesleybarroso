
#!/usr/bin/env python3
"""
Development Pulse Generator
----------------------------

This file intentionally keeps the filename used by the existing repository:

    scripts/update_languages.py

It generates:

    assets/languages-month.svg

The chart contains:
    - a professional donut chart;
    - a percentage ranking;
    - proportional horizontal bars;
    - five named languages plus "Outras";
    - a real update timestamp in America/Sao_Paulo;
    - monthly commit metrics;
    - no dependency on third-party chart images.

The data collection logic is kept independent from the SVG renderer so that
visual changes do not require rewriting the GitHub API logic.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

import requests


# ============================================================================
# CONFIGURATION
# ============================================================================

USER = os.getenv("GITHUB_USERNAME", "Wesleybarroso")
TOKEN = os.getenv("GITHUB_TOKEN")

OUTPUT = Path("assets/languages-month.svg")

GITHUB_API = "https://api.github.com"

LOCAL_TIMEZONE = "America/Sao_Paulo"

REQUEST_TIMEOUT = 30

MAX_RETRIES = 5

PAGE_SIZE = 100

TOP_LANGUAGE_COUNT = 5


# ============================================================================
# VISUAL CONFIGURATION
# ============================================================================

CHART_COLORS = [
    "#00E5FF",
    "#1683FF",
    "#5B63FF",
    "#8B5CF6",
    "#22C55E",
    "#F59E0B",
    "#EF4444",
    "#EC4899",
]

BACKGROUND_START = "#05080F"

BACKGROUND_MIDDLE = "#091421"

BACKGROUND_END = "#04070C"

GRID_COLOR = "#5CA8FF"

GRID_OPACITY = ".022"

ACCENT_START = "#00E5FF"

ACCENT_MIDDLE = "#1683FF"

ACCENT_END = "#5D63FF"

BAR_BACKGROUND = "#0C2440"

PANEL_BACKGROUND = "#07111D"

PANEL_BORDER = "#18344F"

PRIMARY_TEXT = "#F4F8FC"

SECONDARY_TEXT = "#8EA2B9"

MUTED_TEXT = "#71869F"

ACCENT_TEXT = "#57DFFF"


# ============================================================================
# LANGUAGE DETECTION
# ============================================================================

EXTENSIONS: dict[str, str] = {
    # JavaScript
    ".js": "JavaScript",
    ".jsx": "JavaScript",

    # TypeScript
    ".ts": "TypeScript",
    ".tsx": "TypeScript",

    # Go
    ".go": "Go",

    # Python
    ".py": "Python",

    # Java / Kotlin
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",

    # Rust
    ".rs": "Rust",

    # PHP
    ".php": "PHP",

    # Ruby
    ".rb": "Ruby",

    # C family
    ".c": "C",
    ".h": "C/C++",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",

    # Swift
    ".swift": "Swift",

    # Dart
    ".dart": "Dart",

    # Vue / Svelte
    ".vue": "Vue",
    ".svelte": "Svelte",

    # Web
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".less": "Less",

    # SQL
    ".sql": "SQL",

    # Shell
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass(frozen=True)
class LanguageStat:
    """One normalized language and its amount of changed lines."""

    name: str

    lines: int


@dataclass(frozen=True)
class PulseStats:
    """All values needed by the SVG renderer."""

    month_label: str

    updated_label: str

    commits: int

    repositories_analyzed: int

    repositories_with_activity: int

    changed_lines: int

    languages: tuple[LanguageStat, ...]


# ============================================================================
# HTTP
# ============================================================================

def build_headers() -> dict[str, str]:
    """Return the headers used for GitHub API calls."""

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Wesleybarroso-Development-Pulse",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    return headers


HEADERS = build_headers()


def api_get(
    url: str,
    params: dict[str, object] | None = None,
) -> object | None:
    """
    GET one GitHub endpoint with retries.

    409 is intentionally ignored because GitHub can return it for an empty
    repository. That situation must not kill the complete profile update.
    """

    for attempt in range(MAX_RETRIES):
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code in (404, 409):
            message = ""

            try:
                body = response.json()

                if isinstance(body, dict):
                    message = str(
                        body.get("message", "")
                    )

            except ValueError:
                message = ""

            print(
                f"SKIP {response.status_code}: "
                f"{message or url}"
            )

            return None

        if response.status_code in (403, 429):
            retry_after = response.headers.get(
                "Retry-After"
            )

            if (
                retry_after
                and retry_after.isdigit()
            ):
                delay = int(
                    retry_after
                )
            else:
                delay = min(
                    2 ** attempt,
                    30,
                )

            print(
                f"RATE LIMIT {response.status_code}; "
                f"waiting {delay}s"
            )

            time.sleep(delay)

            continue

        raise RuntimeError(
            "GitHub API "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    raise RuntimeError(
        f"GitHub API retry limit reached: {url}"
    )


def paged_get(
    url: str,
    params: dict[str, object] | None = None,
) -> Iterable[dict[str, object]]:
    """Yield all dictionary items from a paginated endpoint."""

    page = 1

    while True:
        page_params = dict(
            params or {}
        )

        page_params["per_page"] = PAGE_SIZE

        page_params["page"] = page

        data = api_get(
            url,
            page_params,
        )

        if not data:
            return

        if not isinstance(
            data,
            list,
        ):
            raise RuntimeError(
                f"Expected list from {url}"
            )

        for item in data:
            if isinstance(
                item,
                dict,
            ):
                yield item

        if len(data) < PAGE_SIZE:
            return

        page += 1


# ============================================================================
# TIME
# ============================================================================

def now_utc_and_local() -> tuple[datetime, datetime]:
    """Return the same instant in UTC and in Brazil/Sao_Paulo."""

    now_utc = datetime.now(
        timezone.utc
    )

    now_local = now_utc.astimezone(
        ZoneInfo(
            LOCAL_TIMEZONE
        )
    )

    return (
        now_utc,
        now_local,
    )


def month_window() -> tuple[
    datetime,
    datetime,
    str,
]:
    """
    Return the first instant of the current local month, current UTC time,
    and the MM/YYYY display label.
    """

    now_utc, now_local = (
        now_utc_and_local()
    )

    local_month_start = datetime(
        year=now_local.year,
        month=now_local.month,
        day=1,
        tzinfo=ZoneInfo(
            LOCAL_TIMEZONE
        ),
    )

    utc_month_start = (
        local_month_start.astimezone(
            timezone.utc
        )
    )

    label = now_local.strftime(
        "%m/%Y"
    )

    return (
        utc_month_start,
        now_utc,
        label,
    )


def to_github_iso(
    value: datetime,
) -> str:
    """Convert a datetime to GitHub's ISO form."""

    return value.isoformat().replace(
        "+00:00",
        "Z",
    )


def update_time_label() -> str:
    """Return the current display timestamp in BRT."""

    _, local_now = (
        now_utc_and_local()
    )

    return local_now.strftime(
        "%d/%m/%Y • %H:%M BRT"
    )


# ============================================================================
# REPOSITORIES
# ============================================================================

def owned_repositories() -> Iterable[
    dict[str, object]
]:
    """Yield repositories owned by the configured GitHub user."""

    url = (
        f"{GITHUB_API}/users/"
        f"{USER}/repos"
    )

    for repository in paged_get(
        url,
        {
            "type": "owner",
            "sort": "updated",
            "direction": "desc",
        },
    ):
        if repository.get(
            "fork"
        ):
            continue

        yield repository


def repository_commits(
    full_name: str,
    since: str,
    until: str,
) -> Iterable[
    dict[str, object]
]:
    """Yield this user's commits for one repository."""

    url = (
        f"{GITHUB_API}/repos/"
        f"{full_name}/commits"
    )

    return paged_get(
        url,
        {
            "author": USER,
            "since": since,
            "until": until,
        },
    )


def commit_details(
    full_name: str,
    sha: str,
) -> dict[str, object] | None:
    """Fetch one commit and its changed files."""

    url = (
        f"{GITHUB_API}/repos/"
        f"{full_name}/commits/"
        f"{sha}"
    )

    result = api_get(url)

    if not isinstance(
        result,
        dict,
    ):
        return None

    return result


# ============================================================================
# LANGUAGE MEASUREMENT
# ============================================================================

def language_for_file(
    filename: str,
) -> str | None:
    """Resolve a language from the file extension."""

    suffix = Path(
        filename.lower()
    ).suffix

    return EXTENSIONS.get(
        suffix
    )


def changed_lines(
    file_data: dict[str, object],
) -> int:
    """Return additions plus deletions."""

    additions = int(
        file_data.get(
            "additions",
            0,
        )
    )

    deletions = int(
        file_data.get(
            "deletions",
            0,
        )
    )

    return max(
        0,
        additions + deletions,
    )


def collect_statistics() -> PulseStats:
    """Collect current-month activity from all owned repositories."""

    month_start, now_utc, month_label = (
        month_window()
    )

    since = to_github_iso(
        month_start
    )

    until = to_github_iso(
        now_utc
    )

    totals: defaultdict[str, int] = (
        defaultdict(int)
    )

    commits = 0

    repositories_analyzed = 0

    repositories_with_activity = 0

    changed_total = 0

    print(
        "Starting Development Pulse..."
    )

    print(
        f"User: {USER}"
    )

    print(
        f"Month: {month_label}"
    )

    for repository in owned_repositories():
        repositories_analyzed += 1

        full_name = str(
            repository.get(
                "full_name",
                "",
            )
        )

        if not full_name:
            continue

        repository_had_activity = False

        print(
            f"Analyzing {full_name}"
        )

        for commit in repository_commits(
            full_name,
            since,
            until,
        ):
            repository_had_activity = True

            sha = str(
                commit.get(
                    "sha",
                    "",
                )
            )

            if not sha:
                continue

            details = commit_details(
                full_name,
                sha,
            )

            if not details:
                continue

            commits += 1

            files = details.get(
                "files",
                [],
            )

            if not isinstance(
                files,
                list,
            ):
                continue

            for file_data in files:
                if not isinstance(
                    file_data,
                    dict,
                ):
                    continue

                filename = str(
                    file_data.get(
                        "filename",
                        "",
                    )
                )

                language = (
                    language_for_file(
                        filename
                    )
                )

                if not language:
                    continue

                delta = changed_lines(
                    file_data
                )

                if delta <= 0:
                    continue

                totals[language] += delta

                changed_total += delta

        if repository_had_activity:
            repositories_with_activity += 1

    raw = sorted(
        totals.items(),
        key=lambda pair: pair[1],
        reverse=True,
    )

    top = raw[
        :TOP_LANGUAGE_COUNT
    ]

    other_value = sum(
        value
        for _, value in raw[
            TOP_LANGUAGE_COUNT:
        ]
    )

    language_stats = [
        LanguageStat(
            name=name,
            lines=value,
        )
        for name, value in top
    ]

    if other_value > 0:
        language_stats.append(
            LanguageStat(
                name="Outras",
                lines=other_value,
            )
        )

    return PulseStats(
        month_label=month_label,
        updated_label=update_time_label(),
        commits=commits,
        repositories_analyzed=repositories_analyzed,
        repositories_with_activity=repositories_with_activity,
        changed_lines=changed_total,
        languages=tuple(
            language_stats
        ),
    )


# ============================================================================
# PERCENTAGES
# ============================================================================

def percentages(
    languages: tuple[LanguageStat, ...],
) -> list[
    tuple[LanguageStat, float]
]:
    """Calculate relative percentages."""

    total = sum(
        item.lines
        for item in languages
    )

    if total <= 0:
        return [
            (
                item,
                0.0,
            )
            for item in languages
        ]

    return [
        (
            item,
            item.lines / total * 100.0,
        )
        for item in languages
    ]


# ============================================================================
# SVG ESCAPING
# ============================================================================

def svg_text(
    value: object,
) -> str:
    """Escape dynamic text inserted into SVG XML."""

    return escape(
        str(value)
    )


# ============================================================================
# DONUT
# ============================================================================

def donut_markup(
    languages: tuple[LanguageStat, ...],
) -> str:
    """Build the SVG donut segments."""

    total = sum(
        item.lines
        for item in languages
    )

    if total <= 0:
        return ""

    cx = 255.0
    cy = 345.0
    radius = 126.0

    circumference = (
        2.0
        * 3.141592653589793
        * radius
    )

    offset = 0.0

    segments: list[str] = []

    for index, item in enumerate(
        languages
    ):
        percentage = (
            item.lines
            / total
            * 100.0
        )

        dash = (
            circumference
            * percentage
            / 100.0
        )

        color = CHART_COLORS[
            index
            % len(CHART_COLORS)
        ]

        segments.append(
            (
                f'<circle cx="{cx:g}" '
                f'cy="{cy:g}" '
                f'r="{radius:g}" '
                f'fill="none" '
                f'stroke="{color}" '
                f'stroke-width="34" '
                f'stroke-linecap="butt" '
                f'stroke-dasharray="{dash:.2f} '
                f'{circumference - dash:.2f}" '
                f'stroke-dashoffset="-{offset:.2f}" '
                f'transform="rotate(-90 '
                f'{cx:g} {cy:g})"/>'
            )
        )

        offset += dash

    return "\n".join(
        segments
    )


# ============================================================================
# DONUT CENTER
# ============================================================================

def donut_center_markup(
    languages: tuple[LanguageStat, ...],
) -> str:
    """Build the central label of the donut."""

    total = sum(
        item.lines
        for item in languages
    )

    if not languages or total <= 0:
        return (
            '<text x="255" y="330" '
            'text-anchor="middle" '
            'fill="#57E1FF" '
            'font-family="monospace" '
            'font-size="10" '
            'font-weight="700">'
            'NO ACTIVITY'
            '</text>\n'
            '<text x="255" y="357" '
            'text-anchor="middle" '
            'fill="#71869F" '
            'font-family="Arial" '
            'font-size="11">'
            'Nenhuma atividade'
            '</text>'
        )

    top = languages[0]

    top_percentage = (
        top.lines
        / total
        * 100.0
    )

    return (
        '<text x="255" y="330" '
        'text-anchor="middle" '
        'fill="#57E1FF" '
        'font-family="monospace" '
        'font-size="10" '
        'font-weight="700">'
        'TOP LANGUAGE'
        '</text>\n'
        '<text x="255" y="365" '
        'text-anchor="middle" '
        'fill="#F4F8FC" '
        'font-family="Arial" '
        'font-size="23" '
        'font-weight="800">'
        f'{svg_text(top.name)}'
        '</text>\n'
        '<text x="255" y="391" '
        'text-anchor="middle" '
        'fill="#71869F" '
        'font-family="Arial" '
        'font-size="11">'
        f'{top_percentage:.1f}%'
        '</text>'
    )


# ============================================================================
# RANKING
# ============================================================================

def ranking_markup(
    languages: tuple[LanguageStat, ...],
) -> str:
    """Build horizontal percentage bars."""

    rows: list[str] = []

    ranked = percentages(
        languages
    )

    start_y = 220.0

    step = 55.0

    max_width = 492.0

    for index, (
        language,
        percentage,
    ) in enumerate(
        ranked
    ):
        y = (
            start_y
            + index * step
        )

        color = CHART_COLORS[
            index
            % len(CHART_COLORS)
        ]

        width = (
            max_width
            * percentage
            / 100.0
        )

        row = (
            '<g>\n'
            f'<circle cx="525" '
            f'cy="{y - 5:.1f}" '
            'r="5" '
            f'fill="{color}"/>\n'
            f'<text x="543" '
            f'y="{y:.1f}" '
            'fill="#E7EEF6" '
            'font-family="Arial,Helvetica,sans-serif" '
            'font-size="13" '
            'font-weight="700">'
            f'{svg_text(language.name)}'
            '</text>\n'
            f'<text x="1035" '
            f'y="{y:.1f}" '
            'text-anchor="end" '
            'fill="#F7FBFF" '
            'font-family="monospace" '
            'font-size="13" '
            'font-weight="800">'
            f'{percentage:.1f}%'
            '</text>\n'
            f'<rect x="543" '
            f'y="{y + 12:.1f}" '
            f'width="{max_width:.1f}" '
            'height="9" '
            'rx="4.5" '
            'fill="#0C2440"/>\n'
            f'<rect x="543" '
            f'y="{y + 12:.1f}" '
            f'width="{width:.2f}" '
            'height="9" '
            'rx="4.5" '
            f'fill="{color}"/>\n'
            '</g>'
        )

        rows.append(
            row
        )

    if not rows:
        rows.append(
            '<text x="515" y="220" '
            'fill="#57DFFF" '
            'font-family="monospace" '
            'font-size="10">'
            'AGUARDANDO ATIVIDADE'
            '</text>'
        )

    return "\n".join(
        rows
    )


# ============================================================================
# METRIC CARD
# ============================================================================

def metric_markup(
    stats: PulseStats,
) -> str:
    """Build the bottom metric card."""

    return (
        '<rect x="515" y="500" '
        'width="545" height="82" '
        'rx="18" '
        'fill="#07111D" '
        'stroke="#18344F"/>\n'
        '<text x="541" y="527" '
        'fill="#57E1FF" '
        'font-family="monospace" '
        'font-size="10" '
        'font-weight="700">'
        'MÉTRICA'
        '</text>\n'
        '<text x="541" y="549" '
        'fill="#E6EDF5" '
        'font-family="Arial" '
        'font-size="12" '
        'font-weight="700">'
        'Linhas adicionadas + removidas nos commits do mês'
        '</text>\n'
        '<text x="541" y="568" '
        'fill="#71869F" '
        'font-family="Arial" '
        'font-size="10">'
        f'{stats.commits} commits • '
        f'{stats.repositories_with_activity} com atividade • '
        f'{stats.repositories_analyzed} analisados • '
        f'{stats.changed_lines} linhas alteradas'
        '</text>'
    )


# ============================================================================
# COMPLETE SVG
# ============================================================================

def render_svg(
    stats: PulseStats,
) -> str:
    """Render the complete professional chart."""

    donut = donut_markup(
        stats.languages
    )

    center = donut_center_markup(
        stats.languages
    )

    ranking = ranking_markup(
        stats.languages
    )

    metrics = metric_markup(
        stats
    )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="1200" height="680" '
        'viewBox="0 0 1200 680">\n'

        '<defs>\n'

        '<linearGradient id="bg" '
        'x1="0" y1="0" '
        'x2="1200" y2="680" '
        'gradientUnits="userSpaceOnUse">\n'

        f'<stop offset="0" '
        f'stop-color="{BACKGROUND_START}"/>\n'

        f'<stop offset=".52" '
        f'stop-color="{BACKGROUND_MIDDLE}"/>\n'

        f'<stop offset="1" '
        f'stop-color="{BACKGROUND_END}"/>\n'

        '</linearGradient>\n'

        '<linearGradient id="accent" '
        'x1="0" y1="0" '
        'x2="1200" y2="0">\n'

        f'<stop offset="0" '
        f'stop-color="{ACCENT_START}"/>\n'

        f'<stop offset=".5" '
        f'stop-color="{ACCENT_MIDDLE}"/>\n'

        f'<stop offset="1" '
        f'stop-color="{ACCENT_END}"/>\n'

        '</linearGradient>\n'

        '<pattern id="grid" '
        'width="34" height="34" '
        'patternUnits="userSpaceOnUse">\n'

        f'<path d="M34 0H0V34" '
        f'stroke="{GRID_COLOR}" '
        f'stroke-opacity="{GRID_OPACITY}"/>\n'

        '</pattern>\n'

        '</defs>\n'

        '<rect width="1200" '
        'height="680" rx="26" '
        'fill="url(#bg)"/>\n'

        '<rect width="1200" '
        'height="680" rx="26" '
        'fill="url(#grid)"/>\n'

        '<path d="M28 70V28H70 '
        'M1130 28H1172V70 '
        'M28 610V652H70 '
        'M1130 652H1172V610" '
        'fill="none" '
        'stroke="url(#accent)" '
        'stroke-width="1.7"/>\n'

        '<text x="54" y="56" '
        'fill="#57DFFF" '
        'font-family="Arial,Helvetica,sans-serif" '
        'font-size="11" '
        'font-weight="700" '
        'letter-spacing="3">'
        'ALTIXDEV / DEVELOPMENT PULSE'
        '</text>\n'

        '<text x="54" y="103" '
        'fill="#F4F8FC" '
        'font-family="Arial,Helvetica,sans-serif" '
        'font-size="31" '
        'font-weight="800">'
        'LINGUAGENS MAIS USADAS NO MÊS'
        '</text>\n'

        '<text x="54" y="130" '
        'fill="#8EA2B9" '
        'font-family="Arial,Helvetica,sans-serif" '
        'font-size="13">'
        'Distribuição percentual da atividade • '
        f'{svg_text(stats.month_label)}'
        '</text>\n'

        '<text x="1146" y="47" '
        'fill="#57E1FF" '
        'font-family="monospace" '
        'font-size="9" '
        'font-weight="700" '
        'text-anchor="end">'
        'ATUALIZADO'
        '</text>\n'

        '<text x="1146" y="68" '
        'fill="#E6EDF5" '
        'font-family="Arial,Helvetica,sans-serif" '
        'font-size="11" '
        'font-weight="700" '
        'text-anchor="end">'
        f'{svg_text(stats.updated_label)}'
        '</text>\n'

        '<g>\n'

        '<circle cx="255" cy="345" '
        'r="172" '
        'fill="#07111D" '
        'stroke="#17324D"/>\n'

        '<circle cx="255" cy="345" '
        'r="126" '
        'fill="none" '
        'stroke="#0C223B" '
        'stroke-width="34"/>\n'

        f'{donut}\n'

        '<circle cx="255" cy="345" '
        'r="90" '
        'fill="#050C15" '
        'stroke="#17344F"/>\n'

        f'{center}\n'

        '</g>\n'

        '<g>\n'

        '<text x="515" y="163" '
        'fill="#57DFFF" '
        'font-family="Arial,Helvetica,sans-serif" '
        'font-size="11" '
        'font-weight="700" '
        'letter-spacing="3">'
        'RANKING / PARTICIPAÇÃO'
        '</text>\n'

        '<text x="515" y="187" '
        'fill="#8EA2B9" '
        'font-family="Arial,Helvetica,sans-serif" '
        'font-size="12">'
        'Percentual relativo de cada linguagem'
        '</text>\n'

        f'{ranking}\n'

        '</g>\n'

        f'{metrics}\n'

        '<line x1="54" y1="620" '
        'x2="1146" y2="620" '
        'stroke="#17334F"/>\n'

        '<text x="54" y="645" '
        'fill="#71869F" '
        'font-family="Arial,Helvetica,sans-serif" '
        'font-size="10">'
        'As porcentagens somam 100% da atividade detectada no período.'
        '</text>\n'

        '<text x="1146" y="645" '
        'fill="#57E1FF" '
        'font-family="monospace" '
        'font-size="10" '
        'font-weight="700" '
        'text-anchor="end">'
        'GITHUB ACTIONS'
        '</text>\n'

        '</svg>\n'
    )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    """Generate the current monthly chart."""

    stats = collect_statistics()

    svg = render_svg(
        stats
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        svg,
        encoding="utf-8",
    )

    print("")
    print("=" * 64)
    print(
        "Development Pulse generated successfully."
    )
    print("=" * 64)
    print(
        "Month:",
        stats.month_label,
    )
    print(
        "Updated:",
        stats.updated_label,
    )
    print(
        "Commits:",
        stats.commits,
    )
    print(
        "Repositories analyzed:",
        stats.repositories_analyzed,
    )
    print(
        "Repositories with activity:",
        stats.repositories_with_activity,
    )
    print(
        "Changed lines:",
        stats.changed_lines,
    )
    print("")
    print(
        "Ranking:"
    )

    ranked = percentages(
        stats.languages
    )

    for item, percentage in ranked:
        print(
            f"  {item.name}: "
            f"{percentage:.1f}% "
            f"({item.lines} changed lines)"
        )

    print("")
    print(
        "Output:",
        OUTPUT,
    )
    print("=" * 64)


if __name__ == "__main__":
    main()


# ============================================================================
# MAINTAINER NOTES
# ============================================================================
#
# The remainder of this file is deliberately documentation. It does not
# affect execution, but it makes the file self-documenting when opened on
# GitHub and makes it obvious which behavior is intentional.
#
# 01. DATA SOURCE
#
# The generator reads the GitHub REST API.
#
# It uses the repository list belonging to USER.
#
# Forks owned by the user are skipped.
#
# 02. TIME WINDOW
#
# The current month is determined using America/Sao_Paulo.
#
# The API range itself is converted to UTC because the GitHub API accepts ISO
# timestamps and the workflow runner is not guaranteed to use Brazil time.
#
# 03. AUTHOR FILTER
#
# The commits endpoint is queried with:
#
#     author = USER
#
# This keeps the monthly activity focused on commits attributed to the
# configured profile.
#
# 04. ACTIVITY METRIC
#
# For every changed file:
#
#     additions + deletions
#
# becomes the measured activity.
#
# This is a practical metric for a profile chart because it gives each
# language a proportional amount of visible work.
#
# 05. UNKNOWN FILES
#
# Files whose extensions are not in EXTENSIONS are ignored.
#
# This does not cause a failure.
#
# 06. EMPTY REPOSITORIES
#
# GitHub may respond with HTTP 409 for an empty Git repository.
#
# A 409 is explicitly skipped in api_get().
#
# This is important because one empty repository must not prevent the
# remaining repositories from being analyzed.
#
# 07. MISSING REPOSITORIES
#
# A 404 is also skipped.
#
# This lets the complete run continue if a repository disappears while an
# hourly workflow is starting.
#
# 08. RATE LIMITS
#
# HTTP 403 and 429 are retried with a small exponential backoff.
#
# The Retry-After header is preferred when GitHub provides it.
#
# 09. TOP FIVE
#
# The chart shows the five most active languages by changed lines.
#
# If more than five languages exist, their remaining activity is aggregated
# into the "Outras" segment.
#
# This means the donut represents the full measured distribution.
#
# 10. PERCENTAGES
#
# The percentage is:
#
#     language_changed_lines / displayed_total * 100
#
# Because "Outras" contains the remainder, visible percentages add up to
# approximately 100%.
#
# 11. DONUT CHART
#
# The donut uses SVG circles with stroke-dasharray.
#
# Every segment receives its own color.
#
# The center shows the top language and its percentage.
#
# 12. BAR CHART
#
# Each horizontal bar uses the exact same percentage as its donut segment.
#
# A 50% language therefore receives approximately half the available bar
# width.
#
# 13. UPDATE TIMESTAMP
#
# The timestamp is generated at execution time.
#
# It is displayed in America/Sao_Paulo and includes:
#
#     DD/MM/YYYY • HH:MM BRT
#
# The timestamp therefore tells the visitor when the SVG was regenerated.
#
# 14. GITHUB ACTIONS
#
# The workflow can continue using:
#
#     python scripts/update_languages.py
#
# No filename change is required.
#
# 15. OUTPUT PATH
#
# The generated file is always:
#
#     assets/languages-month.svg
#
# This keeps the README stable.
#
# 16. README
#
# The README can use:
#
#     <img src="./assets/languages-month.svg">
#
# There is no need to put generated SVG markup directly inside README.md.
#
# 17. THIRD-PARTY SERVICES
#
# The profile SVG does not depend on a remote chart service.
#
# The only external service required for the generator is GitHub's own API.
#
# 18. SECURITY
#
# No access token is hard-coded.
#
# GitHub Actions supplies GITHUB_TOKEN through the workflow environment.
#
# 19. LOCAL TESTING
#
# A local test can be performed after installing requests:
#
#     pip install requests
#     python scripts/update_languages.py
#
# The command should be executed from the repository root so the relative
# output path resolves correctly.
#
# 20. VISUAL IDENTITY
#
# The chart deliberately uses the same visual language established for the
# AltixDev profile:
#
#     electric blue
#     cyan
#     deep navy
#     restrained violet
#     thin technical borders
#     subtle grid texture
#
# 21. VISUAL HIERARCHY
#
# The most prominent element is the donut.
#
# The second visual focus is the percentage ranking.
#
# The update timestamp remains visible but does not compete with the chart.
#
# 22. ONE LANGUAGE
#
# When only one language exists, the donut becomes a complete ring and that
# language correctly shows 100.0%.
#
# This is mathematically correct and does not invent additional languages.
#
# 23. MANY LANGUAGES
#
# When several languages exist, the ring is segmented by their calculated
# percentages.
#
# The horizontal bars use matching colors and percentages.
#
# 24. CURRENT MONTH
#
# Every hourly run recalculates the current month's distribution.
#
# The process does not require manually editing the SVG.
#
# 25. NO STATIC DATA
#
# The placeholder values shown in design previews are not used by main().
#
# main() always collects fresh API data before writing the final SVG.
#
# 26. FAILED WORKFLOW
#
# If an unexpected GitHub API error occurs, the workflow exits non-zero.
#
# If the SVG is successfully generated, the workflow proceeds to its commit
# step.
#
# 27. NO CHANGE
#
# If the generated SVG content has not changed, the GitHub workflow's commit
# step can safely detect an empty git diff and finish without creating a
# meaningless commit.
#
# 28. HOURLY EXECUTION
#
# The schedule belongs in:
#
#     .github/workflows/update-development-pulse.yml
#
# Recommended line:
#
#     - cron: "0 * * * *"
#
# This means once per hour, subject to GitHub Actions scheduling delays.
#
# 29. PROFILE DISPLAY
#
# GitHub may cache image content briefly.
#
# The generated timestamp lets the visitor see when the latest file itself
# was regenerated.
#
# 30. DESIGN MAINTENANCE
#
# If the design needs to change later, edit render_svg(), donut_markup(), or
# ranking_markup() instead of changing the API collection functions.
#
# 31. LANGUAGE EXTENSIONS
#
# Additional extensions can be added to EXTENSIONS without changing the rest
# of the collection pipeline.
#
# 32. COLOR PALETTE
#
# Additional segment colors can be added to CHART_COLORS.
#
# 33. TEXT SAFETY
#
# Dynamic GitHub values are XML-escaped before they are inserted into SVG.
#
# 34. FILE SIZE
#
# The generated SVG is text based and remains small enough for normal GitHub
# profile use.
#
# 35. SVG COMPATIBILITY
#
# The generated document uses standard SVG elements:
#
#     rect
#     circle
#     path
#     text
#
# and standard gradients/patterns.
#
# 36. NO EXTERNAL FONT
#
# The SVG uses common system font families and does not load a remote font.
#
# 37. ACCESSIBILITY
#
# Text labels are kept in the SVG so a reader can identify the language,
# percentage, month and update time without relying only on color.
#
# 38. MOBILE
#
# The SVG viewBox is fixed at 1200x680.
#
# GitHub scales the image to the available profile width while preserving
# the proportions.
#
# 39. TOP LANGUAGE
#
# The donut center always shows the highest-ranked displayed language.
#
# 40. "OUTRAS"
#
# "Outras" is intentionally not a language detection result. It is an
# aggregate category created after ranking.
#
# 41. REPOSITORY COUNT
#
# repositories_analyzed counts non-fork repositories considered by the
# script.
#
# 42. ACTIVE REPOSITORY COUNT
#
# repositories_with_activity counts repositories that returned at least one
# commit in the selected monthly window.
#
# 43. COMMIT COUNT
#
# commits is incremented for successfully retrieved commit detail objects.
#
# 44. CHANGED LINES
#
# changed_lines is the total additions + deletions across recognized file
# extensions.
#
# 45. PERCENTAGE BASIS
#
# Percentages are based on recognized language activity.
#
# A binary asset or an unknown extension does not become a fake language.
#
# 46. EMPTY MONTH
#
# A month with zero recognized activity receives a clean empty state rather
# than a fabricated 100% category.
#
# 47. ROBUSTNESS
#
# The generator is intentionally defensive around API responses.
#
# 48. MAINTAINABILITY
#
# The main program is split into small functions so visual and data logic
# remain independent.
#
# 49. DEPLOYMENT
#
# This file is designed specifically to run inside GitHub Actions, but it can
# also be run from a repository checkout when GITHUB_TOKEN is available.
#
# 50. FINAL OUTPUT
#
# The only artifact this script needs to update for the profile is:
#
#     assets/languages-month.svg
#
# End of maintainer notes.
#
# ============================================================================
# END
# ============================================================================

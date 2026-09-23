#!/usr/bin/env python3
"""Import daily briefs from a ChatGPT conversation export.

The importer is deliberately offline: it only reads the supplied Markdown file
and the existing archive, and never fetches or rewrites article sources.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


RESPONSE_RE = re.compile(r"(?m)^## Response:\s*$")
WINDOW_PATTERNS = (
    re.compile(
        r"统计窗口\s*[：:]\s*(?:北京时间\s*)?"
        r"(?P<sy>\d{4})年(?P<sm>\d{1,2})月(?P<sd>\d{1,2})日\s*"
        r"(?P<sh>\d{1,2}):(?P<smin>\d{2})\s*"
        r"[-–—]\s*"
        r"(?:(?P<ey>\d{4})年)?(?P<em>\d{1,2})月(?P<ed>\d{1,2})日\s*"
        r"(?P<eh>\d{1,2}):(?P<emin>\d{2})"
    ),
    re.compile(
        r"统计窗口\s*[：:]\s*(?:北京时间\s*)?"
        r"(?P<sy>\d{4})[-年](?P<sm>\d{1,2})[-月](?P<sd>\d{1,2})日?\s*"
        r"(?P<sh>\d{1,2}):(?P<smin>\d{2})\s*"
        r"[-–—]\s*"
        r"(?:(?P<ey>\d{4})[-年])?(?P<em>\d{1,2})[-月](?P<ed>\d{1,2})日?\s*"
        r"(?P<eh>\d{1,2}):(?P<emin>\d{2})"
    ),
)
FOOTER_RE = re.compile(r"\n---\s*\n\s*\*\*Powered by \[ChatGPT Exporter\].*?\s*$", re.S)
TRACKING_PARAM_RE = re.compile(r"(?:\?|&)utm_source=chatgpt\.com(?=[)#\s]|$)")


@dataclass
class Brief:
    date: dt.date
    window_start: dt.datetime
    window_end: dt.datetime
    body: str
    response_number: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="ChatGPT export Markdown file")
    parser.add_argument("--dry-run", action="store_true", help="parse and report without writing files")
    parser.add_argument("--output-root", type=Path, default=Path("daily"), help="archive root (default: daily)")
    parser.add_argument("--skip-existing", action="store_true", help="skip every existing archive, including incomplete files")
    parser.add_argument("--repair-incomplete", action="store_true", help="replace an existing archive only when it fails completeness checks")
    parser.add_argument("--keep-tracking-params", action="store_true", help="keep the known ChatGPT utm_source parameter")
    return parser.parse_args()


def parse_datetime(match: re.Match[str], prefix: str) -> dt.datetime:
    year = int(match.group(f"{prefix}y"))
    month = int(match.group(f"{prefix}m"))
    day = int(match.group(f"{prefix}d"))
    hour = int(match.group(f"{prefix}h"))
    minute = int(match.group(f"{prefix}min"))
    return dt.datetime(year, month, day, hour, minute)


def parse_window(body: str) -> tuple[dt.datetime, dt.datetime] | None:
    for pattern in WINDOW_PATTERNS:
        match = pattern.search(body)
        if not match:
            continue
        start = parse_datetime(match, "s")
        end_year = match.group("ey")
        end = parse_datetime(match, "e") if end_year else dt.datetime(
            start.year,
            int(match.group("em")),
            int(match.group("ed")),
            int(match.group("eh")),
            int(match.group("emin")),
        )
        if not end_year and end < start:
            end = end.replace(year=start.year + 1)
        return start, end
    return None


def clean_body(body: str, keep_tracking_params: bool) -> str:
    body = FOOTER_RE.sub("", body).strip()
    if not keep_tracking_params:
        body = TRACKING_PARAM_RE.sub("", body)
    return body.rstrip() + "\n"


def parse_export(source: Path, keep_tracking_params: bool) -> tuple[list[Brief], list[str]]:
    text = source.read_text(encoding="utf-8-sig")
    markers = list(RESPONSE_RE.finditer(text))
    briefs: list[Brief] = []
    failures: list[str] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = clean_body(text[marker.end():end], keep_tracking_params)
        window = parse_window(body)
        has_title = re.search(r"^#\s+.*每日F1.*全球赛车", body, re.M) is not None
        if window is None or not has_title:
            reason = []
            if window is None:
                reason.append("window not recognized")
            if not has_title:
                reason.append("daily-brief title not found")
            failures.append(f"Response {index + 1}: {', '.join(reason)}")
            continue
        start, finish = window
        briefs.append(Brief(finish.date(), start, finish, body, index + 1))
    return briefs, failures


def front_matter(brief: Brief) -> str:
    date = brief.date.isoformat()
    return (
        "---\n"
        f'title: "F1与全球赛车编辑晨报｜{date}"\n'
        f"date: {date}\n"
        "timezone: Asia/Shanghai\n"
        f'window_start: "{brief.window_start:%Y-%m-%d %H:%M}"\n'
        f'window_end: "{brief.window_end:%Y-%m-%d %H:%M}"\n'
        "type: daily-brief\n"
        "archive_source: chatgpt-history\n"
        "---\n\n"
    )


def rendered(brief: Brief) -> str:
    return front_matter(brief) + brief.body


def is_complete_archive(path: Path, date: dt.date) -> bool:
    if not path.is_file() or path.stat().st_size < 1000:
        return False
    text = path.read_text(encoding="utf-8-sig")
    required = (
        text.startswith("---\n"),
        re.search(rf"^date:\s*{re.escape(date.isoformat())}\s*$", text, re.M) is not None,
        re.search(r"^window_start:\s*\"?\d{4}-\d{2}-\d{2} 07:00", text, re.M) is not None,
        re.search(r"^window_end:\s*\"?\d{4}-\d{2}-\d{2} 07:00", text, re.M) is not None,
        re.search(r"^#\s+.*(?:F1|赛车).*(?:晨报|brief)", text, re.I | re.M) is not None,
        "统计窗口" in text,
        "## Response:" not in text,
    )
    return all(required)


def archive_path(output_root: Path, date: dt.date) -> Path:
    return output_root / f"{date:%Y}" / f"{date:%m}" / f"{date:%Y-%m-%d}.md"


def date_range(start: dt.date, end: dt.date):
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


def rebuild_index(output_root: Path) -> None:
    files = sorted(output_root.glob("????/??/????-??-??.md"), reverse=True)
    grouped: dict[str, list[tuple[dt.date, Path]]] = {}
    for path in files:
        try:
            date = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        grouped.setdefault(f"{date:%Y-%m}", []).append((date, path))
    lines = ["# F1每日晨报归档", "", "按统计窗口结束日期归档，日期从新到旧排列。", ""]
    for month in sorted(grouped, reverse=True):
        lines.extend([f"## {month}", ""])
        for date, path in sorted(grouped[month], reverse=True):
            relative = path.relative_to(output_root).as_posix()
            lines.append(f"- [{date.isoformat()}]({relative})")
        lines.append("")
    (output_root / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.source.is_file():
        print(f"Source not found: {args.source}", file=sys.stderr)
        return 2
    briefs, failures = parse_export(args.source, args.keep_tracking_params)
    dates = [brief.date for brief in briefs]
    counts = Counter(dates)
    duplicates = sorted(date for date, count in counts.items() if count > 1)
    unique_dates = sorted(counts)
    short_briefs = sorted(
        brief.date for brief in briefs if len(brief.body.encode("utf-8")) < 1000
    )
    missing: list[dt.date] = []
    if unique_dates:
        expected = set(date_range(unique_dates[0], unique_dates[-1]))
        missing = sorted(expected - set(unique_dates))

    print(f"Found {len(briefs)} daily briefs")
    for date in unique_dates:
        suffix = " (duplicate)" if counts[date] > 1 else ""
        print(f"{date.isoformat()}{suffix}")
    if duplicates:
        print("Duplicate dates:")
        for date in duplicates:
            print(f"- {date.isoformat()}")
    if missing:
        print("Missing dates:")
        for date in missing:
            print(f"- {date.isoformat()}")
    if failures:
        print("Unrecognized responses:")
        for failure in failures:
            print(f"- {failure}")
    if short_briefs:
        print("Suspiciously short briefs (<1000 bytes):")
        for date in short_briefs:
            print(f"- {date.isoformat()}")

    if args.dry_run:
        return 0 if not failures and not duplicates else 1

    created = 0
    skipped = 0
    repaired = 0
    seen: set[dt.date] = set()
    for brief in briefs:
        if brief.date in seen:
            continue
        seen.add(brief.date)
        path = archive_path(args.output_root, brief.date)
        if path.exists():
            complete = is_complete_archive(path, brief.date)
            if args.skip_existing or complete or not args.repair_incomplete:
                skipped += 1
                status = "complete" if complete else "incomplete"
                print(f"Skip existing ({status}): {path}")
                continue
            path.write_text(rendered(brief), encoding="utf-8")
            repaired += 1
            print(f"Repair incomplete: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered(brief), encoding="utf-8")
        created += 1
        print(f"Create: {path}")

    if args.output_root.is_dir():
        rebuild_index(args.output_root)
    print(f"Created: {created}")
    print(f"Repaired: {repaired}")
    print(f"Skipped existing: {skipped}")
    print(f"Conflicts (duplicate source dates): {len(duplicates)}")
    print(f"Parse failures: {len(failures)}")
    return 0 if not failures and not duplicates else 1


if __name__ == "__main__":
    raise SystemExit(main())

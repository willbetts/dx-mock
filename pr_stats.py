"""Open-issue stats for a GitHub repository."""

import os
import subprocess
import sys
from collections import Counter
from datetime import datetime

import requests

REPO = "cli/cli"
API = f"https://api.github.com/repos/{REPO}/issues"


def token() -> str | None:
    """Prefer an env var; fall back to the gh CLI so nothing is hardcoded."""
    if env := os.environ.get("GITHUB_TOKEN"):
        return env
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def fetch_open_issues(repo: str = REPO) -> tuple[list[dict], int]:
    """Every open issue, and how many pull requests were excluded."""
    headers = {"Accept": "application/vnd.github+json"}
    if t := token():
        headers["Authorization"] = f"Bearer {t}"

    issues: list[dict] = []
    excluded = 0
    url, params = API, {"state": "open", "per_page": 100}

    while url:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        for item in r.json():
            # GitHub models a PR as an issue, so /issues returns both. This
            # key is the only discriminator; there is no query parameter.
            if "pull_request" in item:
                excluded += 1
            else:
                issues.append(item)
        # Follow Link rather than counting pages: GitHub says when to stop.
        url = r.links.get("next", {}).get("url")
        params = None

    return issues, excluded


def top_labels(issues: list[dict], n: int = 5) -> list[tuple[str, int]]:
    counts = Counter(
        label["name"] for issue in issues for label in issue.get("labels", [])
    )
    return counts.most_common(n)


def oldest(issues: list[dict], n: int = 5) -> list[dict]:
    # created_at is ISO 8601 in UTC, so a string sort is already chronological.
    return sorted(issues, key=lambda i: i["created_at"])[:n]


def age_in_days(iso: str) -> int:
    created = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(created.tzinfo) - created).days


def main() -> int:
    try:
        issues, excluded = fetch_open_issues()
    except requests.HTTPError as e:
        print(f"GitHub returned {e.response.status_code}", file=sys.stderr)
        return 1

    print(f"\n{REPO}\n")
    print(f"Open issues: {len(issues)}   ({excluded} pull requests excluded)\n")

    print("Top 5 labels")
    width = max((len(n) for n, _ in top_labels(issues)), default=0)
    for name, count in top_labels(issues):
        print(f"  {name:<{width}}  {count}")

    print("\n5 oldest open issues")
    for i in oldest(issues):
        date = i["created_at"][:10]
        print(f"  #{i['number']:<7} {date}  ({age_in_days(i['created_at']):>5}d)  "
              f"{i['title'][:58]}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

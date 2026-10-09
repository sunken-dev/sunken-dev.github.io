#!/usr/bin/env python3
"""Collect the organisation's public projects into projects.json.

A repository's social preview only appears in the og:image tag of its public
page - the same tag link scrapers read. The REST API does not carry it and the
GraphQL field needs a token, so the tag is read here rather than in the browser,
which cannot reach it because GitHub sends no CORS header on repository pages.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

ORG = "sunken-dev"
SELF = "sunken-dev.github.io"
OUTPUT = "projects.json"
# repositories carrying this topic are left out
INTERNAL_TOPIC = "internal"
TIMEOUT = 20

OG_TAG = re.compile(r"""<meta[^>]*property=["']og:image["'][^>]*>""", re.I)
OG_CONTENT = re.compile(r"""content=["']([^"']+)["']""", re.I)


def fetch(url, accept=None, token=None):
    headers = {"User-Agent": f"{ORG}-pages"}
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", "replace")


def social_preview(html):
    """Pull og:image out of a repository page. Attribute order is not fixed."""
    tag = OG_TAG.search(html)
    if not tag:
        return None
    content = OG_CONTENT.search(tag.group(0))
    return content.group(1) if content else None


def collect(token):
    repos = json.loads(
        fetch(
            f"https://api.github.com/orgs/{ORG}/repos?per_page=100&sort=updated",
            "application/vnd.github+json",
            token,
        )
    )

    projects = []
    for repo in repos:
        # forks are someone else's work, and this site is not one of its projects
        if repo["fork"] or repo["name"] == SELF:
            continue
        if INTERNAL_TOPIC in (repo.get("topics") or []):
            continue

        try:
            image = social_preview(fetch(repo["html_url"]))
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"  {repo['name']}: no preview ({error})", file=sys.stderr)
            image = None

        projects.append(
            {
                "name": repo["name"],
                "description": repo["description"],
                "url": repo["html_url"],
                "homepage": repo["homepage"] or None,
                "image": image,
                "topics": repo.get("topics") or [],
            }
        )

    return projects


def main():
    projects = collect(os.environ.get("GH_TOKEN"))
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(projects, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    previews = sum(1 for project in projects if project["image"])
    print(f"collected {len(projects)} projects, {previews} with a preview")


if __name__ == "__main__":
    main()

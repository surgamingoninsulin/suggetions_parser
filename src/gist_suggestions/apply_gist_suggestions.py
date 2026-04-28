#!/usr/bin/env python3
"""
Minecraft Control Panel - Gist Suggestion Importer v2

Reads matching GitHub Issues and appends suggestion items to a Gist provider JSON.

Rules:
- No fenced ```json block is required.
- The script parses JSON from the "Suggestion payload:" section in the issue body.
- Only these top-level sections are imported: plugins, datapacks, mods.
- resourcepacks and unknown sections are ignored.
- Only the inner objects inside each list are appended.
- The wrapper object itself is never appended.
- Issues are selected by title prefix (default: "[Issue Suggestion]").
- New items are appended at the bottom of the matching list.
- Duplicate IDs are skipped.
"""

from __future__ import annotations

import json
import os
import sys
from json import JSONDecodeError
from typing import Any, Dict, List, Optional, Tuple

import requests

GITHUB_API = "https://api.github.com"
VALID_KEYS = ("plugins", "datapacks", "mods")


def env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


def issue_headers() -> Dict[str, str]:
    token = env("GITHUB_ISSUE_TOKEN", required=True)
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Minecraft-Control-Panel-Gist-Suggestions",
    }


def gist_headers() -> Dict[str, str]:
    token = env("GIST_TOKEN") or env("GITHUB_ISSUE_TOKEN", required=True)
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Minecraft-Control-Panel-Gist-Suggestions",
    }


def request_json(method: str, url: str, headers: Dict[str, str], **kwargs: Any) -> Any:
    response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if response.status_code >= 400:
        print(f"GitHub API error {response.status_code} for {method} {url}", file=sys.stderr)
        print(response.text, file=sys.stderr)
    response.raise_for_status()
    return response.json() if response.text else None


def list_suggestion_issues() -> List[Dict[str, Any]]:
    repo = env("GITHUB_REPOSITORY", required=True)
    issue_title_prefix = env("ISSUE_TITLE_PREFIX", "[Issue Suggestion]").strip().lower()

    issues = request_json(
        "GET",
        f"{GITHUB_API}/repos/{repo}/issues",
        issue_headers(),
        params={
            "state": "open",
            "per_page": 100,
            "sort": "created",
            "direction": "asc",
        },
    )

    filtered: List[Dict[str, Any]] = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        title = str(issue.get("title") or "").strip().lower()
        if issue_title_prefix and not title.startswith(issue_title_prefix):
            continue
        filtered.append(issue)
    return filtered


def strip_json_line_comments(text: str) -> str:
    """
    Allows this in suggestions:

      {
        "plugins": [ // comment
          {}
        ]
      }

    Removes // comments only outside strings.
    """
    result: List[str] = []
    in_string = False
    escape = False
    i = 0

    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if escape:
            result.append(char)
            escape = False
            i += 1
            continue

        if char == "\\" and in_string:
            result.append(char)
            escape = True
            i += 1
            continue

        if char == '"':
            result.append(char)
            in_string = not in_string
            i += 1
            continue

        if not in_string and char == "/" and nxt == "/":
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue

        result.append(char)
        i += 1

    return "".join(result)


def find_first_json_object(text: str) -> Dict[str, Any]:
    """
    Finds the first valid JSON object anywhere in the issue body.
    Text before and after the JSON is ignored.
    """
    cleaned = strip_json_line_comments(text or "")
    decoder = json.JSONDecoder()

    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            parsed, _end_index = decoder.raw_decode(cleaned[index:])
        except JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("No valid JSON object found in issue body.")


def extract_payload_section(text: str) -> str:
    """
    Extracts the text after 'Suggestion payload:' when present.
    Falls back to full body when marker does not exist.
    """
    body = text or ""
    marker = "suggestion payload:"
    lower_body = body.lower()
    marker_index = lower_body.find(marker)

    if marker_index < 0:
        return body

    return body[marker_index + len(marker):].strip()


def validate_item(category: str, item: Dict[str, Any], index: int) -> None:
    required = [
        "id",
        "name",
        "author",
        "version",
        "image",
        "directDownloadUrl",
        "description",
        "websiteUrl",
    ]

    if category in ("plugins", "mods"):
        required.append("minecraftVersion")

    if category == "datapacks":
        if "minecraftversion" not in item and "minecraftVersion" not in item:
            raise ValueError(
                f"`datapacks[{index}]` must contain `minecraftversion` or `minecraftVersion`."
            )

    if category == "mods":
        required.append("type")

    missing = [field for field in required if field not in item]
    if missing:
        raise ValueError(f"`{category}[{index}]` is missing fields: {', '.join(missing)}")

    if not str(item.get("id", "")).strip():
        raise ValueError(f"`{category}[{index}].id` cannot be empty.")


def extract_items_only(wrapper: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Only extracts objects from supported sections.

    Example input:
      {
        "plugins": [ {"id": "example-plugin"} ],
        "resourcepacks": [ {"id": "ignored"} ]
      }

    Example output:
      {
        "plugins": [ {"id": "example-plugin"} ],
        "datapacks": [],
        "mods": []
      }
    """
    result: Dict[str, List[Dict[str, Any]]] = {key: [] for key in VALID_KEYS}
    found_supported_key = False

    for key in VALID_KEYS:
        value = wrapper.get(key)
        if value is None:
            continue

        found_supported_key = True

        if not isinstance(value, list):
            raise ValueError(f"`{key}` must be a list.")

        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(f"`{key}[{index}]` must be an object.")
            validate_item(key, item, index)
            result[key].append(item)

    if not found_supported_key:
        raise ValueError(
            "JSON did not contain any supported section. Supported sections: "
            + ", ".join(VALID_KEYS)
        )

    return result


def get_gist_file() -> Tuple[Dict[str, Any], str]:
    gist_id = env("GIST_ID", required=True)
    gist_filename = env("GIST_FILENAME", "gist_provider.json")

    gist = request_json("GET", f"{GITHUB_API}/gists/{gist_id}", gist_headers())
    files = gist.get("files", {})

    if gist_filename not in files:
        available = ", ".join(files.keys())
        raise RuntimeError(f"Gist file `{gist_filename}` not found. Available files: {available}")

    content = files[gist_filename].get("content") or "{}"

    try:
        provider = json.loads(content)
    except JSONDecodeError as exc:
        raise RuntimeError(f"Gist file `{gist_filename}` contains invalid JSON: {exc}") from exc

    if not isinstance(provider, dict):
        raise RuntimeError(f"Gist file `{gist_filename}` must contain a JSON object.")

    for key in VALID_KEYS:
        provider.setdefault(key, [])
        if not isinstance(provider[key], list):
            raise RuntimeError(f"Gist key `{key}` must be a list.")

    return provider, gist_filename


def append_items(provider: Dict[str, Any], suggestions: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    summary = {
        "added": {key: 0 for key in VALID_KEYS},
        "skipped_duplicates": {key: 0 for key in VALID_KEYS},
    }

    for key in VALID_KEYS:
        existing_ids = {
            str(item.get("id"))
            for item in provider.get(key, [])
            if isinstance(item, dict) and item.get("id") is not None
        }

        for item in suggestions.get(key, []):
            item_id = str(item.get("id"))
            if item_id in existing_ids:
                summary["skipped_duplicates"][key] += 1
                continue

            provider[key].append(item)
            existing_ids.add(item_id)
            summary["added"][key] += 1

    return summary


def update_gist_file(provider: Dict[str, Any], gist_filename: str) -> None:
    gist_id = env("GIST_ID", required=True)

    payload = {
        "description": "Minecraft Control Panel provider suggestions",
        "files": {
            gist_filename: {
                "content": json.dumps(provider, ensure_ascii=False, indent=2)
            }
        },
    }

    request_json("PATCH", f"{GITHUB_API}/gists/{gist_id}", gist_headers(), json=payload)


def process_issue(issue: Dict[str, Any]) -> bool:
    issue_number = int(issue["number"])

    try:
        payload_text = extract_payload_section(issue.get("body") or "")
        wrapper = find_first_json_object(payload_text)
        suggestions = extract_items_only(wrapper)

        provider, gist_filename = get_gist_file()
        append_items(provider, suggestions)
        update_gist_file(provider, gist_filename)
        return True

    except Exception as exc:
        print(f"Issue #{issue_number} failed: {exc}", file=sys.stderr)
        return False


def main() -> None:
    issues = list_suggestion_issues()

    if not issues:
        print("No matching suggestion issues found.")
        return

    success = 0
    failed = 0

    for issue in issues:
        if process_issue(issue):
            success += 1
        else:
            failed += 1

    print(f"Done. Success: {success}. Failed: {failed}.")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

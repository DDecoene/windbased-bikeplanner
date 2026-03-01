"""Post to Facebook Page and update history.

Usage: python post_facebook.py <post_file>

Requires env vars: FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_PAGE_ID
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path(".github/data/facebook_history.json")


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posts": []}


def save_history(history):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def parse_post_and_strategy(raw_text):
    """Parse post text and strategy from Claude's output."""
    lines = raw_text.strip().split("\n")
    post_text = lines[0].strip().strip('"').strip("'").strip()
    strategy = ""
    for line in reversed(lines):
        line = line.strip()
        if line and line != post_text:
            strategy = line
            break
    return post_text, strategy


def main():
    post_file = Path(sys.argv[1])
    raw_text = post_file.read_text().strip()

    weather_file = Path("/tmp/weather.json")
    province = ""
    if weather_file.exists():
        weather = json.loads(weather_file.read_text())
        province = weather.get("province", "")

    post_text, strategy = parse_post_and_strategy(raw_text)

    print(f"Facebook post ({len(post_text)} chars):")
    print(f'  "{post_text}"')
    print(f"  Strategy: {strategy}")
    print(f"  Province: {province}")
    print()

    page_id = os.environ["FACEBOOK_PAGE_ID"]
    access_token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]

    url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
    data = urllib.parse.urlencode({
        "message": post_text,
        "access_token": access_token,
    }).encode()

    print("Posting to Facebook...")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Facebook API error {e.code}: {error_body}")
        raise

    post_id = result["id"]
    print(f"Posted! Post ID: {post_id}")

    history = load_history()
    history["posts"].append({
        "text": post_text,
        "date": datetime.now().isoformat(),
        "platform_id": post_id,
        "province": province,
        "strategy": strategy,
        "character_count": len(post_text),
    })

    save_history(history)
    print(f"History updated. Total Facebook posts: {len(history['posts'])}")


if __name__ == "__main__":
    main()

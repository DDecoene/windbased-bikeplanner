"""Post to Twitter/X and update history.

Usage: python post_tweet.py <post_file>
"""
import tweepy
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path(".github/data/post_history.json")


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posts": []}


def save_history(history):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def parse_post_and_strategy(raw_text):
    """Parse post text and strategy from Claude's output.

    Expected format:
    <post text>

    <strategy-name>
    """
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

    # Load weather to get province
    weather_file = Path("/tmp/weather.json")
    province = ""
    if weather_file.exists():
        weather = json.loads(weather_file.read_text())
        province = weather.get("province", "")

    post_text, strategy = parse_post_and_strategy(raw_text)

    if len(post_text) > 280:
        print(f"Tweet too long ({len(post_text)} chars), truncating...")
        post_text = post_text[:277] + "..."

    print(f"Tweet ({len(post_text)} chars):")
    print(f'  "{post_text}"')
    print(f"  Strategy: {strategy}")
    print(f"  Province: {province}")
    print()

    twitter = tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
    )

    print("Posting to Twitter/X...")
    response = twitter.create_tweet(text=post_text)
    tweet_id = response.data["id"]
    print(f"Posted! Tweet ID: {tweet_id}")

    history = load_history()
    history["posts"].append({
        "text": post_text,
        "date": datetime.now().isoformat(),
        "platform_id": tweet_id,
        "province": province,
        "strategy": strategy,
        "character_count": len(post_text),
    })

    save_history(history)
    print(f"History updated. Total Twitter posts: {len(history['posts'])}")


if __name__ == "__main__":
    main()

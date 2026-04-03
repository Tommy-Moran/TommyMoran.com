#!/usr/bin/env python3
"""
T-Minus 400 Social Media Sync
Runs nightly via GitHub Actions to update goals-data.json
based on recent @t-minus-400 posts on TikTok and Instagram.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("anthropic not installed")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent.parent
DATA_FILE = REPO_ROOT / "tminus400" / "goals-data.json"

SYSTEM_PROMPT = """You are a social media research assistant for the T-Minus 400 project.

T-Minus 400 is a 400-day public accountability project by Tommy Moran — a doctor and musician
based in Melbourne, Australia. The project started Feb 22, 2026 and ends Mar 29, 2027.

Social accounts:
- TikTok: @t-minus-400  (https://www.tiktok.com/@t-minus-400)
- Instagram: @t-minus-400 (https://www.instagram.com/t-minus-400)

The 11 goals (use these exact IDs):
  music-release         — 6-track original project released on Spotify / Apple Music
  live-performance      — Perform original music at a ticketed public event or festival
  screenplay-sale       — Complete full-length screenplay, sold or optioned
  half-marathon-pr      — Albert Park Half Marathon Jul 12 2026, beat 5:11/km baseline
  strength-targets      — Bench 85kg×5, Squat 130kg×5, Deadlift 110kg×5 in one session
  hockey-premier        — Melbourne Sharks, appear in >50% of regular-season games
  ecfmg-certification   — USMLE Step 1 + Step 2 CK + full ECFMG certification
  manuscript-publication — Author on peer-reviewed journal publication
  conference-presentation — ALREADY COMPLETE (Mar 20 2026, cardiology conference)
  fracp-completion      — FRACP cardiology qualification
  net-zero              — Student bank debt fully offset by savings

Your job: Search for recent posts from @t-minus-400 on TikTok and Instagram.

For every post you find, try to determine:
- Which goal(s) it relates to
- Whether it signals a goal completion, major milestone, or progress update
- Exact or approximate date of the post
- Key facts from the caption, comments, and any transcript

Be thorough — try multiple search queries. Read post captions carefully.
Look for numbers, dates, results, and any language indicating a goal is done.

Return ONLY a valid JSON object, no other text, with this structure:
{
  "goal_states": {
    "<goal-id>": {
      "status": "complete|in-progress|not-started",
      "completed_date": "YYYY-MM-DD or null",
      "notes": "1-2 sentence description or null",
      "evidence": [{"url": "post URL", "label": "brief label"}]
    }
  },
  "timeline_events": [
    {
      "date": "YYYY-MM-DD",
      "label": "Short milestone label",
      "description": "More detail",
      "type": "event",
      "goal_id": "goal-id"
    }
  ],
  "recent_videos": [
    {
      "url": "https://www.tiktok.com/@t-minus-400/video/<video-id>",
      "goal_id": "goal-id or null",
      "caption": "Post caption excerpt"
    }
  ],
  "updates": [
    {
      "date": "YYYY-MM-DD",
      "goal_id": "goal-id",
      "text": "Plain English update for the feed",
      "evidence_url": "URL or null"
    }
  ]
}

Only include items you have actual evidence for. Do not invent or guess.
If you find nothing new, return empty arrays/objects for each key.
"""


def load_current_data():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        "last_updated": None,
        "financial": {
            "debt_total_start": None,
            "debt_remaining": None,
            "savings": None,
            "note": "Financial data not yet available."
        },
        "goal_states": {},
        "timeline_events": [],
        "recent_videos": [],
        "updates": []
    }


def merge_updates(current, new_data):
    status_rank = {"not-started": 0, "in-progress": 1, "complete": 2, "failed": 3}

    # Merge goal states — only upgrade status, never downgrade
    for goal_id, new_state in new_data.get("goal_states", {}).items():
        existing = current["goal_states"].get(goal_id, {})
        existing_rank = status_rank.get(existing.get("status", "not-started"), 0)
        new_rank = status_rank.get(new_state.get("status", "not-started"), 0)
        if new_rank >= existing_rank:
            current["goal_states"][goal_id] = {**existing, **new_state}

    # Merge timeline events — deduplicate by (date, label)
    existing_keys = {(e["date"], e["label"]) for e in current.get("timeline_events", [])}
    for event in new_data.get("timeline_events", []):
        key = (event["date"], event["label"])
        if key not in existing_keys:
            current.setdefault("timeline_events", []).append(event)
            existing_keys.add(key)

    # Merge videos — deduplicate by URL, keep latest 6
    existing_urls = {v["url"] for v in current.get("recent_videos", [])}
    new_videos = []
    for video in new_data.get("recent_videos", []):
        if video["url"] not in existing_urls:
            new_videos.append(video)
            existing_urls.add(video["url"])
    current["recent_videos"] = (new_videos + current.get("recent_videos", []))[:6]

    # Merge updates — deduplicate by (date, goal_id)
    existing_update_keys = {(u["date"], u["goal_id"]) for u in current.get("updates", [])}
    for update in new_data.get("updates", []):
        key = (update["date"], update["goal_id"])
        if key not in existing_update_keys:
            current.setdefault("updates", []).append(update)
            existing_update_keys.add(key)

    current["last_updated"] = date.today().isoformat()
    return current


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    return json.loads(text)


def run_sync():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("No ANTHROPIC_API_KEY set — skipping sync")
        sys.exit(0)

    client = anthropic.Anthropic(api_key=api_key)
    today = date.today().isoformat()

    print(f"Searching for recent @t-minus-400 posts (today: {today})...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 12
        }],
        messages=[{
            "role": "user",
            "content": f"""Today is {today}.

Search thoroughly for recent posts and activity from @t-minus-400.

Try all of these searches:
1. site:tiktok.com "@t-minus-400"
2. site:instagram.com "t-minus-400"
3. tiktok "t-minus-400" Tommy Moran
4. "t-minus-400" Melbourne doctor musician 2026
5. TikTok @t-minus-400 latest videos
6. instagram t-minus-400 recent posts

For any TikTok videos you find, also search for their transcripts and read the comments.
Look carefully at captions for goal-related language:
- Music (recording, mixing, release, Spotify)
- Running (km times, training, race)
- Gym/lifting (weights, PRs)
- Medical exams (USMLE, Step 1, Step 2, ECFMG)
- Research / publications / conferences
- Hockey (Melbourne Sharks, games played)
- Screenwriting / screenplay
- Finance / debt / savings

Return only the JSON object."""
        }]
    )

    # Extract final text block
    result_text = ""
    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            result_text = block.text

    if not result_text.strip():
        print("No text response from Claude — nothing to update")
        return

    try:
        new_data = extract_json(result_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print("Raw response:", result_text[:800])
        return

    current = load_current_data()
    updated = merge_updates(current, new_data)

    with open(DATA_FILE, "w") as f:
        json.dump(updated, f, indent=2)

    print(f"goals-data.json updated — last_updated: {updated['last_updated']}")

    # Summary
    gs = updated.get("goal_states", {})
    complete = sum(1 for g in gs.values() if g.get("status") == "complete")
    print(f"Goals complete: {complete}/11")
    print(f"Videos tracked: {len(updated.get('recent_videos', []))}")
    print(f"Updates in feed: {len(updated.get('updates', []))}")


if __name__ == "__main__":
    run_sync()

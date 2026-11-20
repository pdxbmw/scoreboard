import requests
import json
import os
import re
import time
from pathlib import Path
from datetime import datetime, timedelta

# Window for the main scoreboard (keep small for speed)
DAYS_BACK = 5
DAYS_FORWARD = 5

LEAGUES = [
    {"key": "nfl", "sport": "football", "league_slug": "nfl", "url": "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", "name": "NFL"},
    {"key": "ncaa_fb", "sport": "football", "league_slug": "college-football", "url": "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard", "name": "College Football"},
    {"key": "nba", "sport": "basketball", "league_slug": "nba", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", "name": "NBA"},
    {"key": "wnba", "sport": "basketball", "league_slug": "wnba", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard", "name": "WNBA"},
    {"key": "ncaa_mb", "sport": "basketball", "league_slug": "mens-college-basketball", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard", "name": "Men's College Hoops"},
    {"key": "ncaa_wb", "sport": "basketball", "league_slug": "womens-college-basketball", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard", "name": "Women's College Hoops"}
]

LIVE_STATUS_RE = re.compile(
    r'(q\d|halftime|\bot\b|\d+:\d+\s*-\s*\d+(?:st|nd|rd|th)|in progress)',
    re.I,
)

def get_date_str(offset):
    return (datetime.now() + timedelta(days=offset)).strftime('%Y%m%d')

def pretty_date_from_str(date_str):
    d = datetime.strptime(date_str, '%Y%m%d')
    return d.strftime('%A, %b %d')

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
TEAMS_DIR = DATA_DIR / "teams" / "sports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
TEAMS_DIR.mkdir(parents=True, exist_ok=True)

all_data = {}
teams_to_fetch = set() # Stores unique (id, sport, league_slug)

def extract_rank(comp):
    try:
        rk = comp.get('curatedRank', {}).get('current')
        if rk is None:
            rk = comp.get('rank')
        return rk
    except Exception:
        return None

def looks_live(status, completed):
    if completed:
        return False
    return bool(LIVE_STATUS_RE.search(status or ''))

def pick_side(competitors, side):
    by_side = {c.get('homeAway'): c for c in competitors or []}
    if side in by_side:
        return by_side[side]
    if side == 'home':
        return (competitors or [None])[0]
    return (competitors or [None, None])[1]

def fetch_day(date_str):
    date_key = pretty_date_from_str(date_str)
    print(f"Processing {date_key}...")
    daily_games = []

    for league in LEAGUES:
        try:
            full_url = f"{league['url']}?dates={date_str}"
            resp = requests.get(full_url, timeout=30).json()

            for event in resp.get('events', []):
                comp = event['competitions'][0]
                home = pick_side(comp.get('competitors'), 'home')
                away = pick_side(comp.get('competitors'), 'away')
                if not home or not away:
                    continue

                if 'id' in home.get('team', {}):
                    teams_to_fetch.add((home['team']['id'], league['sport'], league['league_slug']))
                if 'id' in away.get('team', {}):
                    teams_to_fetch.add((away['team']['id'], league['sport'], league['league_slug']))

                game_data = {
                    "id": event['id'],
                    "league": league['name'],
                    "league_key": league['key'],
                    "sport": league['sport'],
                    "league_slug": league['league_slug'],
                    "date_label": date_key,
                    "status": event['status']['type']['shortDetail'],
                    "completed": event['status']['type']['completed'],
                    "home": {
                        "id": home['team']['id'],
                        "name": home['team']['shortDisplayName'],
                        "score": home['score'],
                        "logo": home['team'].get('logo', ''),
                        "color": f"#{home['team'].get('color', '333333')}",
                        "record": (home.get('records') or [{'summary': '0-0'}])[0]['summary'],
                        "rank": extract_rank(home)
                    },
                    "away": {
                        "id": away['team']['id'],
                        "name": away['team']['shortDisplayName'],
                        "score": away['score'],
                        "logo": away['team'].get('logo', ''),
                        "color": f"#{away['team'].get('color', '333333')}",
                        "record": (away.get('records') or [{'summary': '0-0'}])[0]['summary'],
                        "rank": extract_rank(away)
                    }
                }
                daily_games.append(game_data)
        except Exception as e:
            print(f"  warn {league['key']} {date_str}: {e}")

    return daily_games

# Load existing scores first so we can refresh stuck incomplete days
scores_path = DATA_DIR / 'scores.json'
old_data = {}
if scores_path.exists():
    try:
        with scores_path.open() as f:
            old_data = json.load(f)
    except Exception:
        old_data = {}

dates_to_fetch = {get_date_str(offset) for offset in range(-DAYS_BACK, DAYS_FORWARD + 1)}

# Re-fetch any older days that still look mid-game so they don't freeze forever
stuck_dates = set()
for date_str, games in old_data.items():
    if not isinstance(games, list):
        continue
    if any(looks_live(g.get('status'), g.get('completed')) for g in games):
        stuck_dates.add(date_str)
        dates_to_fetch.add(date_str)

if stuck_dates:
    print(f"--- Also refreshing {len(stuck_dates)} stuck in-progress date(s): {', '.join(sorted(stuck_dates))} ---")

# 1. FETCH MAIN SCOREBOARD
print("--- Fetching Scoreboard ---")
for date_str in sorted(dates_to_fetch):
    all_data[date_str] = fetch_day(date_str)

merged = dict(old_data)
merged.update(all_data)  # overwrite only the dates we just fetched

with scores_path.open('w') as f:
    json.dump(merged, f)

def slim_team_schedule(data, league_key=None):
    """Keep only fields team.html needs so committed JSON stays small."""
    team = data.get('team') or {}
    events = []
    for ev in data.get('events') or []:
        comp = (ev.get('competitions') or [None])[0]
        if not comp:
            continue
        competitors = []
        for c in comp.get('competitors') or []:
            t = c.get('team') or {}
            logos = t.get('logos') or []
            logo0 = logos[0].get('href') if logos and isinstance(logos[0], dict) else (t.get('logo') or '')
            competitors.append({
                'homeAway': c.get('homeAway'),
                'score': c.get('score'),
                'team': {
                    'id': t.get('id'),
                    'displayName': t.get('displayName'),
                    'shortDisplayName': t.get('shortDisplayName') or t.get('name'),
                    'abbreviation': t.get('abbreviation'),
                    'color': t.get('color'),
                    'logos': [{'href': logo0}] if logo0 else [],
                }
            })
        status = (comp.get('status') or {}).get('type') or {}
        events.append({
            'date': ev.get('date'),
            'name': ev.get('name'),
            'competitions': [{
                'status': {'type': {
                    'completed': status.get('completed'),
                    'shortDetail': status.get('shortDetail'),
                }},
                'competitors': competitors,
            }]
        })
    return {
        'league_key': league_key or data.get('league_key'),
        'league': league_key or data.get('league') or data.get('league_key'),
        'team': {
            'id': team.get('id'),
            'displayName': team.get('displayName'),
            'shortDisplayName': team.get('shortDisplayName') or team.get('name'),
            'abbreviation': team.get('abbreviation'),
            'color': team.get('color'),
            'logo': team.get('logo'),
            'recordSummary': team.get('recordSummary'),
        },
        'events': events,
    }

# 2. FETCH INDIVIDUAL TEAM HISTORIES (optional; skipped when SKIP_TEAM_HISTORY=1)
if os.environ.get("SKIP_TEAM_HISTORY", "").lower() in ("1", "true", "yes"):
    print(f"--- Skipping team history fetch ({len(teams_to_fetch)} teams) ---")
else:
    print(f"--- Fetching History for {len(teams_to_fetch)} Teams ---")

    for (team_id, sport, league_slug) in teams_to_fetch:
        try:
            # Fetch the FULL schedule for this team
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league_slug}/teams/{team_id}/schedule"
            data = requests.get(url, timeout=30).json()
            league_key = next((lg["key"] for lg in LEAGUES if lg["sport"] == sport and lg["league_slug"] == league_slug), None)
            slim = slim_team_schedule(data, league_key)

            # Save to data/teams/sports/{sport}/{league_slug}/{TEAM_ID}.json
            team_path = TEAMS_DIR / sport / league_slug / f"{team_id}.json"
            team_path.parent.mkdir(parents=True, exist_ok=True)
            with team_path.open('w') as f:
                json.dump(slim, f)

        except Exception as e:
            print(f"Failed to fetch team {team_id}: {e}")

        # Sleep briefly to be nice to ESPN's API
        time.sleep(0.1)

print("--- Update Complete ---")

import requests
import json
import os
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

def get_date_str(offset):
    return (datetime.now() + timedelta(days=offset)).strftime('%Y%m%d')

def pretty_date(offset):
    d = datetime.now() + timedelta(days=offset)
    return d.strftime('%A, %b %d')

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
TEAMS_DIR = DATA_DIR / "teams"

DATA_DIR.mkdir(parents=True, exist_ok=True)
TEAMS_DIR.mkdir(parents=True, exist_ok=True)

all_data = {}
teams_to_fetch = set() # Stores unique (id, sport, league_slug)

# 1. FETCH MAIN SCOREBOARD
print("--- Fetching Scoreboard ---")
for offset in range(-DAYS_BACK, DAYS_FORWARD + 1):
    date_str = get_date_str(offset)
    date_key = pretty_date(offset)
    print(f"Processing {date_key}...")
    
    daily_games = []
    
    for league in LEAGUES:
        try:
            full_url = f"{league['url']}?dates={date_str}"
            resp = requests.get(full_url).json()
            
            for event in resp.get('events', []):
                comp = event['competitions'][0]
                home = comp['competitors'][0]
                away = comp['competitors'][1]
                
                # Capture teams for deep history fetching later
                if 'id' in home['team']:
                    teams_to_fetch.add((home['team']['id'], league['sport'], league['league_slug']))
                if 'id' in away['team']:
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
                        "record": home.get('records', [{'summary':'0-0'}])[0]['summary']
                    },
                    "away": {
                        "id": away['team']['id'],
                        "name": away['team']['shortDisplayName'],
                        "score": away['score'],
                        "logo": away['team'].get('logo', ''),
                        "color": f"#{away['team'].get('color', '333333')}",
                        "record": away.get('records', [{'summary':'0-0'}])[0]['summary']
                    }
                }
                daily_games.append(game_data)
        except Exception:
            pass

    all_data[date_str] = daily_games

# Save Main Scoreboard (preserve older dates)
scores_path = DATA_DIR / 'scores.json'
old_data = {}
if scores_path.exists():
    try:
        with scores_path.open() as f:
            old_data = json.load(f)
    except Exception:
        old_data = {}

merged = dict(old_data)
merged.update(all_data)  # overwrite only the dates we just fetched

with scores_path.open('w') as f:
    json.dump(merged, f)

# 2. FETCH INDIVIDUAL TEAM HISTORIES (The Fix for CORS)
print(f"--- Fetching History for {len(teams_to_fetch)} Teams ---")

for (team_id, sport, league_slug) in teams_to_fetch:
    try:
        # Fetch the FULL schedule for this team
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league_slug}/teams/{team_id}/schedule"
        data = requests.get(url).json()
        
        # Save to data/teams/TEAM_ID.json
        team_path = TEAMS_DIR / f"{team_id}.json"
        with team_path.open('w') as f:
            json.dump(data, f)
            
    except Exception as e:
        print(f"Failed to fetch team {team_id}: {e}")
    
    # Sleep briefly to be nice to ESPN's API
    time.sleep(0.1)

print("--- Update Complete ---")
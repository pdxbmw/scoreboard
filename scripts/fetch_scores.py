import requests
import json
from datetime import datetime, timedelta

# Fetch a tight window for the main page (keeps it fast)
DAYS_BACK = 3
DAYS_FORWARD = 3

# Added 'sport' and 'league_slug' for the new Team Page
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

all_data = {}

for offset in range(-DAYS_BACK, DAYS_FORWARD + 1):
    date_str = get_date_str(offset)
    date_key = pretty_date(offset)
    print(f"Fetching for {date_key}...")
    
    daily_games = []
    
    for league in LEAGUES:
        try:
            full_url = f"{league['url']}?dates={date_str}"
            resp = requests.get(full_url).json()
            
            for event in resp.get('events', []):
                comp = event['competitions'][0]
                home = comp['competitors'][0]
                away = comp['competitors'][1]

                game_data = {
                    "id": event['id'],
                    "league": league['name'],
                    "league_key": league['key'],
                    "sport": league['sport'],        # NEW: needed for deep links
                    "league_slug": league['league_slug'], # NEW: needed for deep links
                    "date_label": date_key,
                    "status": event['status']['type']['shortDetail'],
                    "completed": event['status']['type']['completed'],
                    "home": {
                        "id": home['team']['id'],    # NEW: needed for team history
                        "name": home['team']['shortDisplayName'],
                        "score": home['score'],
                        "logo": home['team'].get('logo', ''),
                        "color": f"#{home['team'].get('color', '333333')}",
                        "record": home.get('records', [{'summary':'0-0'}])[0]['summary']
                    },
                    "away": {
                        "id": away['team']['id'],    # NEW
                        "name": away['team']['shortDisplayName'],
                        "score": away['score'],
                        "logo": away['team'].get('logo', ''),
                        "color": f"#{away['team'].get('color', '333333')}",
                        "record": away.get('records', [{'summary':'0-0'}])[0]['summary']
                    }
                }
                daily_games.append(game_data)
        except Exception as e:
            pass

    all_data[date_str] = daily_games

with open('scores.json', 'w') as f:
    json.dump(all_data, f)
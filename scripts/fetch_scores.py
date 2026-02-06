import requests
import json
import os

# Define the leagues we want
LEAGUES = [
    {"key": "nba", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", "name": "NBA"},
    {"key": "nfl", "url": "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", "name": "NFL"},
    {"key": "ncaa_fb", "url": "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard", "name": "NCAA Football"},
    {"key": "ncaa_bb", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard", "name": "NCAA Men's"}
]

def get_record(competitor):
    """Safe extraction of win/loss records (The math part!)"""
    if 'records' in competitor and competitor['records']:
        return competitor['records'][0]['summary']
    return "0-0"

all_games = []

for league in LEAGUES:
    try:
        print(f"Fetching {league['name']}...")
        resp = requests.get(league['url']).json()
        
        for event in resp.get('events', []):
            comp = event['competitions'][0]
            competitors = comp['competitors']
            
            # Identify Home and Away
            home = next(c for c in competitors if c['homeAway'] == 'home')
            away = next(c for c in competitors if c['homeAway'] == 'away')

            game_data = {
                "league": league['name'],
                "status": event['status']['type']['shortDetail'], # e.g. "Final" or "10:30 4th"
                "completed": event['status']['type']['completed'],
                "home": {
                    "name": home['team']['shortDisplayName'],
                    "score": home['score'],
                    "logo": home['team'].get('logo', ''),
                    "color": f"#{home['team'].get('color', '333333')}", # Default to grey if no color
                    "record": get_record(home),
                    "winner": home.get('winner', False)
                },
                "away": {
                    "name": away['team']['shortDisplayName'],
                    "score": away['score'],
                    "logo": away['team'].get('logo', ''),
                    "color": f"#{away['team'].get('color', '333333')}",
                    "record": get_record(away),
                    "winner": away.get('winner', False)
                }
            }
            all_games.append(game_data)
            
    except Exception as e:
        print(f"Skipping {league['name']} due to error: {e}")

# Save to the root directory so index.html can find it
with open('scores.json', 'w') as f:
    json.dump(all_games, f)
import requests
import json
import os
import time
from datetime import datetime, timedelta

# Only fetch today's games for live updates
TODAY = datetime.now().strftime('%Y%m%d')

LEAGUES = [
    {"key": "nfl", "sport": "football", "league_slug": "nfl", "url": "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", "name": "NFL"},
    {"key": "ncaa_fb", "sport": "football", "league_slug": "college-football", "url": "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard", "name": "College Football"},
    {"key": "nba", "sport": "basketball", "league_slug": "nba", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", "name": "NBA"},
    {"key": "wnba", "sport": "basketball", "league_slug": "wnba", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard", "name": "WNBA"},
    {"key": "ncaa_mb", "sport": "basketball", "league_slug": "mens-college-basketball", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard", "name": "Men's College Hoops"},
    {"key": "ncaa_wb", "sport": "basketball", "league_slug": "womens-college-basketball", "url": "http://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard", "name": "Women's College Hoops"}
]

def is_live_game(status):
    """Check if a game is currently live"""
    if not status:
        return False
    
    # Live game indicators
    live_indicators = ['Q1', 'Q2', 'Q3', 'Q4', 'Halftime', 'OT', 'OT1', 'OT2', 'OT3']
    status_lower = status.lower()
    
    # Check for quarter/time indicators
    for indicator in live_indicators:
        if indicator.lower() in status_lower:
            return True
    
    # Check for time patterns (like "7:30 PM" but not "Final")
    if ('pm' in status_lower or 'am' in status_lower) and 'final' not in status_lower:
        # Additional check - make sure it's not a scheduled game
        if any(char.isdigit() for char in status) and ':' in status:
            # This looks like a time, but could be scheduled or live
            # For now, assume scheduled games are not live
            return False
    
    return False

def fetch_live_games():
    """Fetch only live games for today"""
    print(f"--- Fetching Live Games for {TODAY} ---")
    
    live_games = []
    total_games = 0
    
    # Load existing data to preserve non-live games
    existing_data = {}
    if os.path.exists('../data/scores.json'):
        try:
            with open('../data/scores.json', 'r') as f:
                existing_data = json.load(f)
        except:
            existing_data = {}
    
    for league in LEAGUES:
        try:
            url = f"{league['url']}?dates={TODAY}"
            resp = requests.get(url).json()
            
            for event in resp.get('events', []):
                total_games += 1
                comp = event['competitions'][0]
                status = comp.get('status', {}).get('type', {}).get('shortDetail', '')
                
                if is_live_game(status):
                    print(f"🔴 LIVE: {event.get('shortName', 'Unknown')} - {status}")
                    
                    home = comp['competitors'][0]
                    away = comp['competitors'][1]
                    
                    game_data = {
                        "id": event['id'],
                        "league": league['name'],
                        "league_key": league['key'],
                        "sport": league['sport'],
                        "league_slug": league['league_slug'],
                        "date_label": datetime.now().strftime('%A, %b %d'),
                        "status": status,
                        "completed": comp['status']['type']['completed'],
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
                    live_games.append(game_data)
                else:
                    print(f"⚪ Not live: {event.get('shortName', 'Unknown')} - {status}")
        
        except Exception as e:
            print(f"Error fetching {league['name']}: {e}")
    
    print(f"\nFound {len(live_games)} live games out of {total_games} total games")
    
    # Update existing data with live games
    if TODAY not in existing_data:
        existing_data[TODAY] = []
    
    # Replace today's games with updated data (live games only)
    # Keep non-live games from existing data if they exist
    non_live_existing = [game for game in existing_data.get(TODAY, []) if not is_live_game(game.get('status', ''))]
    
    # Combine non-live existing games with updated live games
    existing_data[TODAY] = non_live_existing + live_games
    
    # Save updated data
    with open('../data/scores.json', 'w') as f:
        json.dump(existing_data, f)
    
    print(f"✅ Updated scores.json with {len(live_games)} live games")
    return len(live_games)

if __name__ == "__main__":
    live_count = fetch_live_games()
    print(f"\n--- Update Complete ---")
    print(f"Live games found: {live_count}")
    
    if live_count > 0:
        print("🔴 Games are live! Scores updated.")
    else:
        print("⚪ No live games currently.")

from db import FotmobDB
from utils import configure_logger

import functools
import json
import os
import time
from urllib.parse import urlparse, parse_qs

import requests

api_host = "https://www.fotmob.com/api"
data_dir = "./data"
no_cache_headers = {"Cache-Control": "no-cache"}

logger = configure_logger()


@functools.lru_cache(maxsize=100)
def get_player(player_id):
    db = FotmobDB()
    player = db.get_player(player_id)
    if player:
        return player
    
    logger.info(f"Getting player {player_id} from api.")
    response = requests.get(f"{api_host}/playerData?id={player_id}", headers=no_cache_headers).json()
    if response:
        db.get_players_table().insert(get_player_core_info(response))
        player = db.get_player(player_id)
        if not player:
            logger.error(f"Player {player_id} not found.")
            return
    
        return player
    

def get_player_core_info(player):
    position_data = player["origin"]["positionDesc"]
    player_props_data = {}
    for prop in player["playerProps"]:
        title = "_".join(prop["title"].split()).lower()
        player_props_data[title] = prop["value"]["key"] or prop["value"]["fallback"]
    
    clubs = []
    career_history_info = player["careerHistory"]
    if career_history_info["fullCareer"]:
        for club in career_history_info["careerData"]["careerItems"]["senior"]:
            if not club["hasUncertainData"]:
                clubs.append({
                    "team_name": club["team"],
                    "team_id": club["teamId"],
                    "transfer_type": club["transferType"],
                    "start_date": club["startDate"],
                    "end_date": club.get("endDate"),
                    "appearances": club["appearances"]
                })

    return {
        "id": player["id"],
        "name": player["name"],
        "on_loan": player["origin"].get("onLoan"),
        "team": {
            "name": player["origin"].get("teamName"),
            "id": player["origin"].get("teamId")
        },
        "primary_position": get_position_short(position_data["primaryPosition"]["label"]),
        "other_positions": [get_position_short(_["label"]) for _ in position_data.get("nonPrimaryPositions", [])],
        "clubs": clubs,
        **player_props_data
    }


@functools.lru_cache(maxsize=100)
def get_league(league_id, default_params={}):
    if not default_params:
        default_params = {
            "tab": "overview",
            "type": "league",
            "timeZone": "America/Los_Angeles"
        }
    params = {"id": league_id, **default_params}
    return requests.get(f"{api_host}/leagues", headers=no_cache_headers, params=params).json()


def get_league_season_totw(league_id, season_year):
    path = f"{data_dir}/totw/{league_id}/{season_year}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            totws = json.load(f)
            if totws:
                return totws
    
    league = get_league(league_id)
    if league:
        # logger.info(f"Getting stat links from league {league_id}")
        totw_links = []
        for item in league["stats"]["seasonStatLinks"]:
            totw_links.append({
                "name": item["Name"],
                "tournament": item["TournamentId"],
                "link": item["TotwRoundsLink"]
            })
    
    rounds_link = None
    for item in totw_links:
        if int(item["name"].split("/")[0]) == int(season_year):
            rounds_link = item["link"]
            logger.info(f"Using rounds link {rounds_link}")
            break

    totws = []
    if rounds_link:
        logger.info(f"Getting TOTW from {rounds_link}.")
        response = requests.get(rounds_link, headers=no_cache_headers).json()
        if response:
            rounds = dict(response).get("rounds")
            if rounds:
                for r in rounds:
                    link = r["link"]
                    totw = requests.get(r["link"]).json()
                    print(totw)
                    round_id = parse_qs(urlparse(link).query)["roundid"][0]
                    logger.info(f"Getting TOTW for {r}. Url: {link}")
                    if totw:
                        logger.success(f"TOTW found for {round_id}")
                        totws.append({"round": round_id, **totw})
                    time.sleep(0.1)

    if totws:
        os.makedirs(os.path.split(path)[0], exist_ok=True)
        with open(path, "w") as f:
            json.dump(totws, f)

    return totws


def group_totw_data(league_id, season_year):
    totws = get_league_season_totw(league_id, season_year)
    totw_ratings = {}
    for team in totws:
        players = team["players"]
        for player in players:
            player_id = player["participantId"]
            rating_info = {
                "match": player["matchId"],
                "rating": player["rating"],
                "motm": bool(player["motm"]),
                "round": team["round"],
                "team": player["teamId"]
            }
            if totw_ratings.get(player_id):
                totw_ratings[player_id].append(rating_info)
            else:
                totw_ratings[player_id] = [rating_info]
    return totw_ratings

def get_league_season_totw_players(league_id, season_year):
    data = group_totw_data(league_id, season_year)
    ids = set(data.keys())
    players = []
    for i in ids:
        player = get_player(i)
        if player:
            players.append(player)
    
    return players


def get_position_short(s):
    return "".join(t[0].upper() for t in s.split())


if __name__ == "__main__":
    from pprint import pprint

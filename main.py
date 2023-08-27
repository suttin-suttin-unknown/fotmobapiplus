import glob
import json
import re
import os
from datetime import datetime
from operator import itemgetter

import requests
from cachetools import cached, TTLCache

api_host = "https://www.fotmob.com/api"
week_in_seconds = 60 * 60 * 24 * 7
no_cache_headers = {"Cache-Control": "no-cache"}


def convert_camel_to_snake(cc_str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cc_str).lower()


@cached(TTLCache(maxsize=50, ttl=week_in_seconds))
def get_league(league_id):
    league_url = f"{api_host}/leagues"
    league = requests.get(league_url, headers=no_cache_headers, params={
        "id": league_id,
        "tab": "overview",
        "type": "league",
        "timeZone": "America/Los_Angeles"
    })
    if hasattr(league, "json"):
        return league.json()
    
    
@cached(TTLCache(maxsize=100, ttl=week_in_seconds))
def get_player(player_id):
    player_url = f"{api_host}/playerData?id={player_id}"
    player = requests.get(player_url)
    if hasattr(player, "json"):
        return player.json()
    

def get_player_primary_info(player_id):
    player = get_player(player_id)
    name = player["name"]
    club = player["origin"].get("teamName", "")
    positions = sorted(player["origin"]["positionDesc"].get("positions", []), key=lambda p: -p["isMainPosition"])
    positions = [position["strPosShort"]["label"] for position in positions]
    age = [prop for prop in player["playerProps"] if prop["title"] == "Age"][0]["value"]["fallback"]
    appearances = get_player_senior_apps(player_id)
    return {
        "name": name,
        "club": club,
        "positions": "/".join(positions),
        "age": age,
        "appearances": appearances
    }
    
    
def get_player_senior_apps(player_id):
    player = get_player(player_id)
    try:
        clubs = player["careerHistory"]["careerData"]["careerItems"]["senior"]
    except TypeError:
        return
    
    total = 0
    for club in clubs:
        apps = club["appearances"]
        if not apps:
            continue
    
        match = re.match(r"(\d+)", apps)
        if match:
            total += int(match.group())

    return total


def get_league_stat_links(league_id):
    keys = ["Name", "RelativePath", "TotwRoundsLink"]
    league = get_league(league_id)
    stat_links = [itemgetter(*keys)(link_dict) for link_dict in league["stats"]["seasonStatLinks"]]
    stat_links = [dict(zip(map(convert_camel_to_snake, keys), link_values)) for link_values in stat_links]
    stat_links = dict([(d["name"].split("/")[0], d) for d in stat_links])
    return stat_links


@cached(TTLCache(maxsize=100, ttl=week_in_seconds))
def get_league_totw_data(league_id, week, year):
    stat_links = get_league_stat_links(league_id)
    totw_rounds_url = stat_links[str(year)]["totw_rounds_link"]
    totw_data = requests.get(totw_rounds_url).json()
    totw_url = totw_data["rounds"][-1 - (week - 1)]["link"]
    totw = requests.get(totw_url).json()
    return totw


def get_league_totw_player_data(league_id, week, year):
    directories = glob.glob(f"league/{league_id}/totw/{year}/{week}/*.json")
    if directories:
        latest = max(directories, key=os.path.getmtime)
        with open(latest, "r") as f:
            return json.load(f)
    
    data = []
    totw = get_league_totw_data(league_id, week, year)
    for player in totw["players"]:
        data.append(get_player_primary_info(player["participantId"]))

    ts = round(float(datetime.now().timestamp()))
    path = f"league/{league_id}/totw/{year}/{week}/{ts}.json"
    os.makedirs(os.path.split(path)[0], exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

    return data


def get_totw_table(league_id, week, year):
    table = []
    player_data = get_league_totw_player_data(league_id, week, year)
    table.append(tuple(player_data[0].keys()))
    table.extend(sorted([tuple(data.values()) for data in player_data], key=lambda v: v[3]))
    return table


def get_totw_table_formatted(table):
    col_widths = [max(len(str(item)) for item in col) for col in zip(*table)]
    formatted_rows = []
    border_line = "+" + "+".join("-" * (width + 2) for width in col_widths) + "+"

    header = table[0]
    formatted_header = "|" + "|".join(str(item).upper().center(width + 2) for item, width, in zip(header, col_widths)) + "|"

    formatted_rows.append(border_line)
    formatted_rows.append(formatted_header)
    formatted_rows.append(border_line)

    for row in table[1:]:
        formatted_row = "|" + "|".join(" " + str(item).ljust(width) + " " for item, width in zip(row, col_widths)) + "|"
        formatted_rows.append(formatted_row)
        formatted_rows.append(border_line)

    return formatted_rows

        
if __name__ == "__main__":
    from pprint import pprint

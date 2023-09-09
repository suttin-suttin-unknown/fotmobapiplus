import glob
import json
import os
import re
import time
from datetime import datetime
from operator import itemgetter

import requests
from cachetools import cached, TTLCache

api_host = "https://www.fotmob.com/api"
data_dir = "./data"
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
    

def get_league_roster(league_id):
    league = get_league(league_id)
    table = league["table"][0]["data"]["table"]["all"]
    return [team["name"] for team in table]


def get_league_transfers(league_id):
    transfers = get_league(league_id)["transfers"]["data"]
    if transfers:
        for transfer in transfers:
            del transfer["position"]
            del transfer["transferText"]
            del transfer["transferType"]
            if transfer.get("fee"):
                value = transfer["fee"].get("value")
                del transfer["fee"]
                transfer["fee"] = value
    return transfers

    
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


def get_player_data_minified(player_id):
    """
    Pulls data from api and shrinks it for db.
    """
    def _parse_origin_data(player_data):
        origin_data = player_data["origin"]
        data = {}
        data["on_loan"] = origin_data["onLoan"]
        data["team_id"] = origin_data["teamId"]
        data["team_name"] = origin_data["teamName"]
        data["positions"] = []
        positions = origin_data["positionDesc"]["positions"]
        for position in positions:
            data["positions"].append({
                "position": position["strPosShort"]["label"], 
                "apps": position["occurences"], 
                "main": position["isMainPosition"]
            })

        return data
    
    def _parse_player_prop_data(player_data):
        props_data = player_data["playerProps"]
        data = {}
        for prop in props_data:
            value = prop["value"]
            prop_key = "_".join([w.lower() for w in prop["title"].split()])
            data[prop_key] = value["key"] or value["fallback"]
        return data
    
    def _parse_career_history_data(player_data):
        parsed_data = {}
        parsed_data["clubs"] = []
        for club in player_data["careerHistory"]["careerData"]["careerItems"]["senior"]:
            if not club["hasUncertainData"]:
                club_data = {
                    "appearances": club["appearances"],
                    "start_date": club["startDate"],
                    "team": club["team"]
                }

                if club.get("endDate"):
                    club_data["end_date"] = club["endDate"]

                parsed_data["clubs"].append(club_data)

        return parsed_data
    
    def _parse_recent_match_data(player_data):
        recent_match_data = player_data["recentMatches"]["All competitions"]
        parsed_data = []
        for match in recent_match_data:
            parsed_data.append({
                "match_id": match["versus"]["matchId"],
                "rating": match["ratingProps"]["num"],
                "rating_color": match["ratingProps"]["bgcolor"] # rating color is kind of random but interesting...
            })

        return {"recent_matches": parsed_data}
    
    def _parse_career_statistics_data(player_data):
        career_statistics_data = player_data["careerStatistics"]
        parsed_data = []
        for league in career_statistics_data:
            league_name = league["name"]
            for season in league["seasons"]:
                try:
                    season_start = season["stats"][0]["startTS"]
                    season_stats = season["stats"][0]["statsArr"]
                    stat_data = {}
                    for stat in season_stats:    
                        value = stat[-1]["value"]
                        stat_key = stat[-1]["key"]
                        if stat_key == "rating_title":
                            stat_data["rating"] = value["num"]
                            stat_data["rating_color"] = value["bgcolor"]
                        elif not re.match(r"^[a-z_][a-z0-9_]*$", stat_key):
                            key = "_".join(stat[0].split()).lower()
                            stat_data[key] = value
                        else:
                            stat_data[stat_key] = value
                    
                    parsed_data.append({
                        "name": league_name,
                        "season_start": season_start,
                        "season_stats": stat_data
                    })
                except IndexError:
                    pass
                
        return {"career_statistics": parsed_data}

    player = get_player(player_id)

    return {
        "id": player["id"],
        "name": player["name"],
        **_parse_origin_data(player),
        **_parse_player_prop_data(player),
        **_parse_recent_match_data(player),
        **_parse_career_statistics_data(player),
        **_parse_career_history_data(player)
    }


def get_league_totw_player_data(league_id, week, year):
    directories = glob.glob(f"{data_dir}/league/{league_id}/totw/{year}/{week}/*.json")
    if directories:
        latest = max(directories, key=os.path.getmtime)
        with open(latest, "r") as f:
            return json.load(f)
    
    data = []
    totw = get_league_totw_data(league_id, week, year)
    for player in totw["players"]:
        data.append(get_player_data_for_db(player["participantId"]))

    ts = round(float(datetime.now().timestamp()))
    path = f"{data_dir}/league/{league_id}/totw/{year}/{week}/{ts}.json"
    os.makedirs(os.path.split(path)[0], exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

    return data


# Probably redundant
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


def get_all_season_totw(league_id, year):
    week = 1
    while True:
        try:
            print(f"Saving data for League {league_id} Week {week}/{year}.")
            print(*get_totw_table_formatted(get_totw_table(league_id, week, year)), sep="\n")
        except IndexError as error:
            print(error)
            break
        except Exception as error:
            print(error)
            print(f"Skipping TOTW player save for League {league_id} Week {week}{year}.")
            time.sleep(5)

        week += 1


if __name__ == "__main__":
    from pprint import pprint

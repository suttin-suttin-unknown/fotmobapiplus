import re
from datetime import datetime
from operator import itemgetter

import requests
from cachetools import cached, TTLCache
from loguru import logger
from tinydb import TinyDB, Query

api_host = "https://www.fotmob.com/api"
data_dir = "./data"
week_in_seconds = 60 * 60 * 24 * 7
no_cache_headers = {"Cache-Control": "no-cache"}


def convert_camel_to_snake(cc_str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cc_str).lower()


class FotmobDB:
    """
    Database for relevant fotmob data.
    """
    _instance = None

    def __new__(cls, db_file="fotmob.json"):
        if cls._instance is None:
            cls._instance = super(FotmobDB, cls).__new__(cls)
            cls._instance.db = TinyDB(db_file)
        return cls._instance
    
    def get_player(self, player_id):
        table = self.db.table("players")
        player = table.get(Query().id == player_id)
        return player
    
    def get_league(self, league_id):
        table = self.db.table("leagues")
        league = table.get(Query().id == league_id)
        return league
    
    def get_totw(self, league_id, season_year, week):
        query = Query()
        table = self.db.table("totw")
        totw = table.get(query.league_id == league_id and query.season_year == season_year and query.week == week)
        return totw

    def upsert_player(self, player, debug=False):
        player_id = player["id"]
        existing_player = self.get_player(player_id)
        table = self.db.table("players")
        if existing_player:    
            if debug:
                logger.debug(f"Player {player_id} exists. Updating.")
            table.update(player, Query().id == player_id)
        else:
            table.insert(player)

    def upsert_league(self, league, debug=False):
        league_id = league["id"]
        existing_league = self.get_league(league_id)
        table = self.db.table("leagues")
        if existing_league:
            if debug:
                logger.debug(f"League {league_id} exists. Updating.")
            table.update(league, Query().id == league_id)
        else:
            table.insert(league)



@cached(TTLCache(maxsize=100, ttl=week_in_seconds))
def get_player(player_id):
    player_url = f"{api_host}/playerData?id={player_id}"
    player = requests.get(player_url)
    if hasattr(player, "json"):
        return player.json()


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
    

def get_league_totw_round_links(league_id):
    league = get_league(league_id)
    if league:
        data = []
        for item in league["stats"]["seasonStatLinks"]:
            keys = ["Name", "TotwRoundsLink", "TournamentId"]
            data.append(dict(zip(keys, itemgetter(*keys)(item))))
    
        return data
    
    
def get_league_totw_links(league_id, season_year):
    data = get_league_totw_round_links(league_id)
    rounds_link = None
    for item in data:
        if int(item["Name"].split("/")[0]) == int(season_year):
            rounds_link = item["TotwRoundsLink"]
            break

    if rounds_link:
        response = requests.get(rounds_link, headers=no_cache_headers).json()
        if response:
            return [r["link"] for r in response["rounds"]]

@cached(TTLCache(maxsize=100, ttl=week_in_seconds))
def get_league_totw(league_id, season_year, week):
    links = get_league_totw_links(league_id, season_year)
    if links:
        link = links[-week]
        response = requests.get(link, headers=no_cache_headers).json()
        return response
    

def get_league_data_minified(league_id):
    def _parse_stats_data(league_data):
        stats = league_data["stats"]
        data = {}
        data["players"] = [stat["fetchAllUrl"] for stat in stats["players"]]
        data["teams"] = [stat["fetchAllUrl"] for stat in stats["teams"]]
        data["seasons"] = []
        for item in stats["seasonStatLinks"]:
            year = item["Name"].split("/")[0]
            totw_rounds_link = item["TotwRoundsLink"]
            tournament_id = item["TournamentId"]
            data["seasons"].append({
                "year": year,
                "totw_rounds_link": totw_rounds_link,
                "tournament_id": tournament_id
            })
        return {"stats": data}
    
    league = get_league(league_id)
    return {
        "id": league["details"]["id"],
        "country": league["details"]["country"],
        **_parse_stats_data(league)
    }


def save_player(player_id):
    player = get_player_data_minified(player_id)
    if player:
        FotmobDB().upsert_player(player)


def save_league(league_id):
    league = get_league_data_minified(league_id)
    if league:
        FotmobDB().upsert_league(league)


def save_totw(league_id, season_year, week):
    db = FotmobDB()
    existing_totw = db.get_totw(league_id, season_year, week)
    if not existing_totw:
        logger.info(f"TOTW League {league_id} Year {season_year} Week {week} not found.")
        totw = get_league_totw(league_id, season_year, week)
        logger.info(f"TOTW data: {totw}")
        totw_table = db.db.table("totw")
        totw_table.insert({
            "league_id": league_id,
            "season_year": season_year,
            "week": week,
            **totw}
        )




# def save_league_totw(league_id, year, week):
#     existing_totw = FotmobDB().get_totw(league_id, year, week)
#     if existing_totw:
#         return existing_totw

#     league = FotmobDB().get_league(league_id)
#     if league:
#         current_year = int(datetime.now().year)
#         seasons_links = league["stats"]["seasons"]
#         totw_rounds_link = seasons_links[int(current_year - year)]["totw_rounds_link"]
#         totw_rounds = requests.get(totw_rounds_link, headers=no_cache_headers).json()["rounds"]
#         if totw_rounds:
#             totw_link = totw_rounds[len(totw_rounds) - week]["link"]
#             if totw_link:
#                 totw = requests.get(totw_link).json()
#                 if totw:
#                     data = []
#                     for player in totw["players"]:
#                         data.append({
#                             "id": player["participantId"],
#                             "match_id": player["matchId"],
#                             "rating": player["rating"],
#                             "motm": bool(player["motm"])
#                         })

#                     data = {
#                         "league": league_id,
#                         "year": year,
#                         "week": week,
#                         "players": data
#                     }

#                     FotmobDB().upsert_totw(data)
#                     return data
                
# def save_league_all_year_totw(league_id, year):
#     logger.info(f"Saving totw data for League {league_id} - Year/Season {year}")
#     week = 1
#     while True:
#         try:
#             save_league_totw(league_id, year, week)
#         except IndexError:
#             break
#         except Exception as error:
#             logger.error(f"Could not save totw data for League {league_id} - Year/Season {year} - Week {week}. Error message: {error}")
#         else:
#             logger.info(f"Saving totw data for League {league_id} - Year/Season {year} - Week {week}")

#         week += 1


    
# def get_league_roster(league_id):
#     league = get_league(league_id)
#     table = league["table"][0]["data"]["table"]["all"]
#     return [team["name"] for team in table]


# def get_league_transfers(league_id):
#     transfers = get_league(league_id)["transfers"]["data"]
#     if transfers:
#         for transfer in transfers:
#             del transfer["position"]
#             del transfer["transferText"]
#             del transfer["transferType"]
#             if transfer.get("fee"):
#                 value = transfer["fee"].get("value")
#                 del transfer["fee"]
#                 transfer["fee"] = value
#     return transfers

    

    
    
# def get_player_senior_apps(player_id):
#     player = get_player(player_id)
#     try:
#         clubs = player["careerHistory"]["careerData"]["careerItems"]["senior"]
#     except TypeError:
#         return
    
#     total = 0
#     for club in clubs:
#         apps = club["appearances"]
#         if not apps:
#             continue
    
#         match = re.match(r"(\d+)", apps)
#         if match:
#             total += int(match.group())

#     return total


# def get_league_stat_links(league_id):
#     keys = ["Name", "RelativePath", "TotwRoundsLink"]
#     league = get_league(league_id)
#     stat_links = [itemgetter(*keys)(link_dict) for link_dict in league["stats"]["seasonStatLinks"]]
#     stat_links = [dict(zip(map(convert_camel_to_snake, keys), link_values)) for link_values in stat_links]
#     stat_links = dict([(d["name"].split("/")[0], d) for d in stat_links])
#     return stat_links


# @cached(TTLCache(maxsize=100, ttl=week_in_seconds))
# def get_league_totw_data(league_id, week, year):
#     stat_links = get_league_stat_links(league_id)
#     totw_rounds_url = stat_links[str(year)]["totw_rounds_link"]
#     totw_data = requests.get(totw_rounds_url).json()
#     totw_url = totw_data["rounds"][-1 - (week - 1)]["link"]
#     totw = requests.get(totw_url).json()
#     return totw


# # cli function
# def save_league_totw_data(league_id, week, year):
#     totw = get_league_totw_data(league_id, week, year)
#     if totw:
#         totw_dir = f"{data_dir}/league/{league_id}/totw/{year}"
#         os.makedirs(totw_dir, exist_ok=True)
#         with open(os.path.join(totw_dir, f"{week}.json"), "w") as f:
#             json.dump([player for player in totw["players"]], f)


def get_player_data_minified(player_id):
    """
    Pulls data from api and shrinks it for db.
    """
    def _parse_origin_data(player_data):
        """
        For origin data in player response
        """
        origin_data = player_data["origin"]
        
        data = {}
        on_loan = origin_data.get("onLoan", None)
        if on_loan != None:
            data["on_loan"] = on_loan
            
        team_id = origin_data.get("teamId")
        if team_id:
            data["team_id"] = team_id

        team_name = origin_data.get("teamName")
        if team_name:
            data["team_name"] = team_name

        data["positions"] = []

        positions = origin_data["positionDesc"].get("positions", [])
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
        career_history_data = player_data["careerHistory"]
        if career_history_data["fullCareer"]:
            for club in career_history_data["careerData"]["careerItems"]["senior"]:
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
        # **_parse_recent_match_data(player),
        # **_parse_career_statistics_data(player),
        **_parse_career_history_data(player)
    }


# def get_league_totw_player_data(league_id, week, year):
#     directories = glob.glob(f"{data_dir}/league/{league_id}/totw/{year}/{week}/*.json")
#     if directories:
#         latest = max(directories, key=os.path.getmtime)
#         with open(latest, "r") as f:
#             return json.load(f)
    
#     data = []
#     totw = get_league_totw_data(league_id, week, year)
#     for player in totw["players"]:
#         data.append(get_player_data_minified(player["participantId"]))

#     ts = round(float(datetime.now().timestamp()))
#     path = f"{data_dir}/league/{league_id}/totw/{year}/{week}/{ts}.json"
#     os.makedirs(os.path.split(path)[0], exist_ok=True)
#     with open(path, "w") as f:
#         json.dump(data, f)

#     return data


# # Probably redundant
# def get_totw_table(league_id, week, year):
#     table = []
#     player_data = get_league_totw_player_data(league_id, week, year)
#     table.append(tuple(player_data[0].keys()))
#     table.extend(sorted([tuple(data.values()) for data in player_data], key=lambda v: v[3]))
#     return table


# def get_totw_table_formatted(table):
#     col_widths = [max(len(str(item)) for item in col) for col in zip(*table)]
#     formatted_rows = []
#     border_line = "+" + "+".join("-" * (width + 2) for width in col_widths) + "+"

#     header = table[0]
#     formatted_header = "|" + "|".join(str(item).upper().center(width + 2) for item, width, in zip(header, col_widths)) + "|"

#     formatted_rows.append(border_line)
#     formatted_rows.append(formatted_header)
#     formatted_rows.append(border_line)

#     for row in table[1:]:
#         formatted_row = "|" + "|".join(" " + str(item).ljust(width) + " " for item, width in zip(row, col_widths)) + "|"
#         formatted_rows.append(formatted_row)
#         formatted_rows.append(border_line)

#     return formatted_rows


# def save_all_season_totw_players(league_id, year):
#     logger.info(f"Saving TOTW data for League {league_id} - {year}")
#     week = 1
#     while True:
#         try:
#             save_totw_player_data(league_id, week, year)
#         except IndexError:
#             break
#         except Exception as error:
#             logger.error(f"{error}. Skipping TOTW player save for League {league_id} Week {week}/{year}.")
#             time.sleep(2)
#         else:
#             logger.info(f"Saving TOTW data for League {league_id} Week {week}/{year}.")

#         week += 1


if __name__ == "__main__":
    from pprint import pprint

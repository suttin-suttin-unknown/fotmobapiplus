from api import get_league_season_totw_players
from db import FotmobDB

from prettytable import PrettyTable
import click


def format_display_table(items):
    table = PrettyTable()
    table.field_names = list(items[0].keys())
    for i in items:
        table.add_row(list(i.values()))
    return table


@click.group()
def cli():
    """
    Cli commands for interacting with player db.
    """
    pass


@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.argument("season_year", type=click.INT, required=True)
def get_league_totw_players(league_id, season_year):
    players = get_league_season_totw_players(league_id, season_year)
    table = []
    for player in players:
        table.append({
            "name": f"{player['name']} ({player['id']})",
            "pos_main": player["primary_position"],
            "pos_other": "/".join(player["other_positions"]),
            "team": f"{player['team']['name']} ({player['team']['id']})",
        })

    print(format_display_table(table))

# @cli.command
# @click.argument("league_id", type=click.INT, required=True)
# @click.argument("season_year", type=click.INT, required=True)
# def get_totw_data(league_id, season_year):
#     data = save_league_totw_season_data(league_id, season_year)
#     logger.info(f"TOTW Data - League: {data['league_id']} - Year: {data['season_year']}")
#     totw = data["totw"]
#     for team in totw:
#         print(f"Round: {team['round']}")
#         try:
#             players = team["players"]
#             print(format_display_table(players))
#         except KeyError:
#             pass


# @cli.command
# @click.argument("league_id", type=click.INT, required=True)
# @click.argument("season_year", type=click.INT, required=True)
# @click.argument("round_id", required=True)
# def save_totw_player_data(league_id, season_year, round_id):
#     data = save_league_totw_season_data(league_id, season_year)
#     round_data = [t for t in data["totw"] if str(round_id) == str(t["round"])]
#     if round_data and len(round_data) == 1:
#         db = FotmobDB()
#         for item in round_data[0]["players"]:
#             player_id = item["participantId"]
#             player = db.get_player(player_id)
#             if player:
#                 print(f"Player {player['id']} exists.")
#             else:
#                 player_data = get_player_data_minified(player_id)
#                 db.get_players_table().insert(player_data)
#                 player = db.get_player(player_id)
#                 print(f"Player {player['id']} saved.")


# @cli.command
# @click.argument("league_id", type=click.INT, required=True)
# @click.argument("season_year", type=click.INT, required=True)
# @click.option("-v", "--verbose", type=click.BOOL, default=False)
# def save_full_season_totw_player_data(league_id, season_year, verbose):
#     param_banner = f"League {league_id} - Season {season_year}/{season_year + 1}"
#     logger.info(f"Saving TOTW player data for {param_banner}")
#     data = save_league_totw_season_data(league_id, season_year)
#     player_ids = set(list(chain(*[[player["participantId"] for player in team["players"]] for team in data["totw"]])))
#     if verbose and not player_ids:
#         print(f"No totw season data saved for {param_banner}.")
#     elif player_ids:
#         db = FotmobDB()
#         for i in player_ids:
#             player = db.get_player(i)
#             if verbose and player:
#                 logger.success(f"Player {i} found in DB.")
#             elif not player:
#                 logger.info(f"Player {i} not found in DB. Fetching...")
#                 player_data = get_player_data_minified(i)
#                 if player_data["id"] == i:
#                     db.get_players_table().insert(player_data)
#                     logger.success(f"Player {i} saved.")
#                 else:
#                     logger.error(f"Fetched player data id doesn't match. Expected id: {i} != Fetched id: {player_data['id']}")


# @cli.command
# @click.argument("league_id", type=click.INT, required=True)
# @click.argument("season_year", type=click.INT, required=True)
# @click.argument("round_id", required=True)
# def get_totw_player_data(league_id, season_year, round_id):
#     data = save_league_totw_season_data(league_id, season_year)
#     round_data = [t for t in data["totw"] if str(round_id) == str(t["round"])]
#     if round_data and len(round_data) == 1:
#         db = FotmobDB()
#         table = []
#         for player in round_data[0]["players"]:
#             player_id = player["participantId"]
#             player_entry = db.get_player(player_id)
#             if player_entry:
#                 positions = player_entry["positions"]
#                 clubs = player_entry["clubs"]
#                 total_apps = 0
#                 for club in clubs:
#                     apps = club["appearances"]
#                     if apps:
#                         print
#                         try:
#                             apps = int(re.sub(r"[^0-9]", "", apps))
#                             total_apps += apps
#                         except Exception:
#                             continue
                
#                 table.append({
#                     "name": player_entry["name"],
#                     "country": player_entry["country"],
#                     "age": player_entry["age"],
#                     "apps": total_apps,
#                     "positions": "/".join([p["position"] for p in sorted(positions, key=lambda d: -d["main"])]),
#                     "team_name": player_entry.get("team_name", "n/a"),
#                     "on_loan": player_entry.get("on_loan", "n/a"),
#                     "market_value": player_entry.get("market_value", "n/a")
#                 })

#         print(format_display_table(sorted(table, key=lambda i: (i["age"], -i["apps"]))))


# @cli.command
# @click.argument("league_id", type=click.INT, required=True)
# @click.argument("season_year", type=click.INT, required=True)
# def get_aggregated_player_list(league_id, season_year):
#     db = FotmobDB()
#     data = save_league_totw_season_data(league_id, season_year)
#     print(data)
#     player_ids = set(list(chain(*[[player["participantId"] for player in team["players"]] for team in data["totw"]])))
#     table = []
    
#     for i in player_ids:
#         player = db.get_player(i)
#         positions = player["positions"]
#         clubs = player["clubs"]
#         total_apps = 0
#         for club in clubs:
#             apps = club["appearances"]
#             if apps:
#                 try:
#                     apps = int(re.sub(r"[^0-9]", "", apps))
#                     total_apps += apps
#                 except Exception:
#                     continue
#         table.append({
#             "name": player["name"],
#             "country": player["country"],
#             "age": player["age"],
#             "apps": total_apps,
#             "positions": "/".join([p["position"] for p in sorted(positions, key=lambda d: -d["main"])]),
#             "team_name": player.get("team_name", "n/a"),
#             "on_loan": player.get("on_loan", "n/a"),
#             "market_value": player.get("market_value", "n/a")
#         })
    
#     print(format_display_table(sorted(table, key=lambda p: p["apps"])))



if __name__ == "__main__":
    cli()

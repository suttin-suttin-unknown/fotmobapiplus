from api import get_player_data_minified, save_league_totw_season_data
from db import FotmobDB
from utils import convert_camel_to_snake

import re
from operator import itemgetter

from loguru import logger
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
def get_totw_data(league_id, season_year):
    data = save_league_totw_season_data(league_id, season_year)
    logger.info(f"TOTW Data - League: {data['league_id']} - Year: {data['season_year']}")
    totw = data["totw"]
    for team in totw:
        print(f"Round: {team['round']}")
        try:
            players = team["players"]
            print(format_display_table(players))
        except KeyError:
            pass


@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.argument("season_year", type=click.INT, required=True)
@click.argument("round_id", required=True)
def save_totw_player_data(league_id, season_year, round_id):
    data = save_league_totw_season_data(league_id, season_year)
    round_data = [t for t in data["totw"] if str(round_id) == str(t["round"])]
    if round_data and len(round_data) == 1:
        db = FotmobDB()
        for item in round_data[0]["players"]:
            player_id = item["participantId"]
            player = db.get_player(player_id)
            if player:
                print(f"Player {player['id']} exists.")
            else:
                player_data = get_player_data_minified(player_id)
                db.get_players_table().insert(player_data)
                player = db.get_player(player_id)
                print(f"Player {player['id']} saved.")


@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.argument("season_year", type=click.INT, required=True)
@click.argument("round_id", required=True)
def get_totw_player_data(league_id, season_year, round_id):
    data = save_league_totw_season_data(league_id, season_year)
    round_data = [t for t in data["totw"] if str(round_id) == str(t["round"])]
    if round_data and len(round_data) == 1:
        db = FotmobDB()
        table = []
        for player in round_data[0]["players"]:
            player_id = player["participantId"]
            player_entry = db.get_player(player_id)
            if player_entry:
                positions = player_entry["positions"]
                clubs = player_entry["clubs"]
                total_apps = 0
                for club in clubs:
                    apps = club["appearances"]
                    if apps:
                        print
                        try:
                            apps = int(re.sub(r"[^0-9]", "", apps))
                            total_apps += apps
                        except Exception:
                            continue

                table.append({
                    "name": player_entry["name"],
                    "country": player_entry["country"],
                    "age": player_entry["age"],
                    "apps": total_apps,
                    "positions": "/".join([p["position"] for p in positions]),
                    "team_name": player_entry["team_name"],
                    "on_loan": player_entry["on_loan"]
                })

        print(format_display_table(sorted(table, key=lambda i: (i["apps"], -i["age"]))))


if __name__ == "__main__":
    cli()

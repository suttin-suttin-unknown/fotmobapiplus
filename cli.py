import api
from db import FotmobDB

import re

from prettytable import PrettyTable
import click


def format_display_table(items):
    table = PrettyTable()
    table.field_names = list(items[0].keys())
    for i in items:
        table.add_row(list(i.values()))
    return table


def get_player_row(player):
    clubs = player["clubs"]
    apps = [int(re.match(r"(\d+)", club["appearances"]).group()) for club in clubs if club["appearances"]]
    return {
        "name": f"{player['name']} ({player['id']})",
        "team": f"{player['team']['name']} ({player['team']['id']})",
        "age": player["age"],
        "apps": sum(apps),
        "market_value": player.get("market_value"),
        "on_loan": player.get("on_loan", "n/a")
    }


@click.group()
def cli():
    """
    Cli commands for interacting with player db.
    """
    pass


@cli.command
@click.argument("player_id", type=click.INT, required=True)
def get_player(player_id):
    player = api.get_player(player_id)
    print(format_display_table([get_player_row(player)]))


@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.argument("season_year", type=click.INT, required=True)
def get_league_totw_players(league_id, season_year):
    players = api.get_league_season_totw_players(league_id, season_year)
    table = []
    for player in players:
        table.append(get_player_row(player))

    print(format_display_table(sorted(table, key=lambda r: (r["age"], -r["apps"]))))


if __name__ == "__main__":
    cli()

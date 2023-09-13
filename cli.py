import api
import utils
from db import FotmobDB

import re
import time
from datetime import datetime

from prettytable import PrettyTable
import click


def format_display_table(items):
    table = PrettyTable()
    table.align = "l"
    table.field_names = list(" ".join(str(t).capitalize() for t in k.split("_")) for k in items[0].keys())
    for i in items:
        table.add_row(list(i.values()))
    return table


def get_player_row(player, short_name=True):
    team = player["team"]["name"]
    if player["on_loan"]:
        team = f"{team} (on loan)"

    clubs = player["clubs"]
    apps = [int(re.match(r"(\d+)", club["appearances"]).group()) for club in clubs if club["appearances"]]
    
    name = player["name"]
    if short_name:
        names = name.split()
        if len(names) == 2:
            f, l = names
            name = f"{f[0]}. {l}"
        elif len(names) > 2:
            f = names[0]
            l = names[1:]
            name = f"{f[0]}. {' '.join(l)}"

    market_value = player.get("market_value")
    if market_value:
        market_value = market_value.lower()

    return {
        "name": name,
        "positions": "/".join(player["positions"]),
        "age": player.get("age"),
        "apps": sum(apps),
        "market_value": market_value,
        "country": utils.get_country_code(player["country"]),
        "team": team or "n/a"
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


filters = {}

@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.argument("season_year", type=click.INT, required=True)
def get_league_totw_players(league_id, season_year):
    groupings = api.group_totw_data(league_id, season_year)
    players = api.get_league_season_totw_players(league_id, season_year)
    table = []
    for player in players:
        row = get_player_row(player)
        row["totw_count"] = None
        totws = groupings.get(player["id"])
        if totws:
            row["totw_count"] = len(totws)
        else:
            row["totw_count"] = 0

        table.append(row)

    print(format_display_table(sorted(table, key=lambda r: (r["age"], -r["apps"]))))


@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.option("-u", "--until", type=click.INT)
def aggregate_totw_data(league_id, until):
    def merge_groupings(*groupings):
        merged = {}
        for g in groupings:
            for k, v in g.items():
                if k in merged:
                    merged[k].extend(v)
                else:
                    merged[k] = v.copy()
        return merged
    
    year = datetime.today().year
    if not until:
        until = year

    season_groupings = []
    while True:
        if year < until:
            break

        season_groupings.append(api.group_totw_data(league_id, year))
        year -= 1

    season_groupings = merge_groupings(*season_groupings)
    player_table = []
    for i in season_groupings:
        player = api.get_player(i)
        if player:
            row = get_player_row(player)
            totws = season_groupings[i]
            if totws:
                row["totw_count"] = len(totws)
            else:
                row["totw_count"] = 0
            player_table.append(row)

    print(f"League {league_id} {until} - {datetime.today().year}")
    print(format_display_table(sorted(player_table, key=lambda r: (r["age"], -r["apps"]))))
    print(format_display_table([{"count": len(player_table)}]))

    # exclude moved


if __name__ == "__main__":
    from pprint import pprint
    cli()

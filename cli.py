import api
import utils

import csv
import glob
import hashlib
import os
import re
import time
from datetime import datetime

from prettytable import PrettyTable
import click


def format_display_table(items):
    table = PrettyTable()
    table.align = "l"
    if items:
        table.field_names = list(" ".join(str(t).capitalize() for t in k.split("_")) for k in items[0].keys())
        for i in items:
            table.add_row(list(i.values()))
        return table


def get_player_row(player, short_name=False):
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

    # all_apps
    # league_apps
    return {
        "name": name,
        "id": player["id"],
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

    print(format_display_table(sorted(table, key=lambda r: (r["age"] or 0, -r["apps"] or 0))))


@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.option("-u", "--until", type=click.INT)
@click.option("-s", "--save", type=click.BOOL, default=True)
def aggregate_totw_data(league_id, until, save):
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
    filters = {
        "max_apps": 110,
        "max_market_value": 700000,
        "in_league": True
    }
    start = time.time()
    print(f"Looking up {len(season_groupings)} players.")
    for i in season_groupings:
        print(f"Getting player {i}")
        player = api.get_player(i)
        if player:
            row = get_player_row(player)
            price = utils.convert_price_string(row["market_value"])
            if row["apps"] <= filters["max_apps"] \
                and (price or 0) < filters["max_market_value"]:
                totws = season_groupings[i]
                if totws:
                    row["totw_count"] = len(totws)
                else:
                    row["totw_count"] = 0
                player_table.append(row)

    end = time.time()
    print(f"Total time: {round(end - start, 2)}s")

    def sort_table(row):
        age = row["age"] or 0
        apps = row["apps"] or 0
        return (age, -apps)

    query_stats_table = [{
        "count": len(player_table)
    }]

    player_table = sorted(player_table, key=sort_table)
    player_keys = list(player_table[0].keys())
    print(player_keys)
    print(format_display_table(player_table))
    print(format_display_table(query_stats_table))

    if save:
        views_dir = "views"
        os.makedirs(views_dir, exist_ok=True)
        path = f"{views_dir}/league_{league_id}_{until}.csv"
        with open(path, "w") as csv_file:
            print(f"Saving player view to {path}.")
            writer = csv.DictWriter(csv_file, fieldnames=player_keys)
            writer.writeheader()
            writer.writerows(player_table)


@cli.command
@click.argument("league_id", type=click.INT, required=True)
@click.option("-u", "--until", type=click.INT)
def get_view(league_id, until):
    if not until:
        until = datetime.today().year
    
    views_dir = "views"
    path = f"{views_dir}/league_{league_id}_{until}.csv"
    if not os.path.exists(path):
        print(f"No view found for expected path {path}")
        return

    table = []
    print(path)
    with open(path, "r") as csv_file:
        print("found.")
        reader = csv.DictReader(csv_file)
        table = [row for row in reader]

    if table:
        print(format_display_table(table))


def dedupe_dict_list(dict_list):
    deduped = []
    hash_count = {}
    for d in dict_list:
        h = hashlib.sha256(str(d).encode()).hexdigest()
        if hash_count.get(h):
            hash_count[h] += 1
        else:
            hash_count[h] = 1

        if hash_count[h] == 1:
            deduped.append(d)

    return deduped


def update_master_table():
    paths = glob.glob("views/*")
    master_table = []
    for path in paths:
        try:
            with open(path, "r") as csv_file:
                reader = csv.DictReader(csv_file)
                master_table.extend([row for row in reader])
        except IsADirectoryError:
            continue

    if len(master_table) > 0:
        with open("views/master.csv", "w") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=master_table[0].keys())
            writer.writeheader()
            writer.writerows(master_table)

def create_master_table():
    update_master_table()
    master_table = []
    with open("views/master.csv", "r") as csv_file:
        reader = csv.DictReader(csv_file)
        master_table = [row for row in reader]

    master_table = dedupe_dict_list(master_table)
    return master_table


@cli.command
def get_master_table():
    master_table = create_master_table()
    filters = {
        "max_age": 25,
        "max_market_value": 330000,
        "min_totw_count": 1
    }
    master_table = list(filter(lambda r: int(r["age"]) <= filters["max_age"], master_table))
    master_table = list(filter(lambda r: int(utils.convert_price_string(r["market_value"]) or 0) <= filters["max_market_value"], master_table))
    master_table = list(filter(lambda r: int(r["totw_count"]) >= filters["min_totw_count"], master_table))
    missing_table = list(filter(lambda r: not r["market_value"], master_table))
    exceptions = []
    with open("views/exceptions/exceptions.csv", "r") as csv_file:
        reader = csv.DictReader(csv_file)
        for r in reader:
            if r.get("market_value"):
                exceptions.append(r)

    exception_names = [e["name"] for e in exceptions]
    
    updated_missing = []
    for i in missing_table:
        name = i["name"]
        if name in exception_names:
            exception = [e for e in exceptions if name == e["name"]]
            if len(exception) == 1:
                n = i.copy()
                n["market_value"] = f"€{exception[0]['market_value']}"
                updated_missing.append(n)

    #print(format_display_table(updated_missing))

    master_complete = list(filter(lambda r: r["market_value"], master_table))
    final_master = master_complete + updated_missing
    final_master = sorted(final_master, key=lambda r: -int(r["totw_count"]))

    filters = {
        "max_market_value": 330000
    }

    # final_master = 
    
    # final_master = [r for r in final_master if (int(utils.convert_price_string(r["market_value"])) or 0) <= filters["max_market_value"]]

    final_master = [r for r in final_master if utils.convert_price_string(r["market_value"])]
    final_master = [r for r in final_master if utils.convert_price_string(r["market_value"]) <= filters["max_market_value"]]
    print(format_display_table(final_master))
    print(len(final_master))

    with open("players.csv", "w") as f:
        writer = csv.DictWriter(f, fieldnames=final_master[0].keys())
        writer.writeheader()
        writer.writerows(final_master)
    #print(format_display_table(sorted(master_table, key=lambda r: -int(r["totw_count"]))))
    



if __name__ == "__main__":
    from pprint import pprint
    cli()

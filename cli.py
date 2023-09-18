import api
import utils

import csv
import glob
import hashlib
import json
import os
import re
import statistics
import time
from datetime import datetime
from itertools import groupby

from prettytable import PrettyTable
import click


def format_display_table(items, field_names=None):
    if not field_names:
        field_names = items[0].keys()
         
    table = PrettyTable()
    table.align = "l"
    if items:
        table.field_names = list(" ".join(str(t).capitalize() for t in k.split("_")) for k in field_names)
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
    start = time.time()
    print(f"Looking up {len(season_groupings)} players...")
    print(f"Expected time: {round(len(season_groupings) /(1.29 * 60), 2)}m")
    for i in season_groupings:
        print(f"Getting player {i}")
        player = api.get_player(i)
        if player:
            row = get_player_row(player)
            totws = season_groupings[i]
            if totws:
                row["totw_count"] = len(totws)
            else:
                row["totw_count"] = 0
            player_table.append(row)
            # price = utils.convert_price_string(row["market_value"])
            # if row["apps"] <= filters["max_apps"] \
            #     and (price or 0) < filters["max_market_value"]:
                

    end = time.time()
    print(f"Total time: {round((end - start) / 60, 2)}m")

    def sort_table(row):
        age = row["age"] or 0
        apps = row["apps"] or 0
        return (age, -apps)

    query_stats_table = [{
        "count": len(player_table)
    }]

    player_table = sorted(player_table, key=sort_table)
    player_keys = list(player_table[0].keys())
    # print(player_keys)
    # print(format_display_table(player_table))
    # print(format_display_table(query_stats_table))

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
        print(format_display_table([{"count": len(table)}]))


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
@click.option("-mn_a", "--min-age", type=click.INT)
@click.option("-mx_a", "--max-age", type=click.INT)
@click.option("-mn_mv", "--min-market-value", type=click.INT)
@click.option("-mx_mv", "--max-market-value", type=click.INT)
@click.option("-mn_tw", "--min-totw", type=click.INT)
@click.option("-mx_tw", "--max-totw", type=click.INT)
@click.option("-s", "--sort", type=click.STRING)
def get_master_table(min_age, max_age, min_market_value, max_market_value, min_totw, max_totw, sort):
    master_table = create_master_table()

    if min_age:
        _master_table = []
        for row in master_table:
            age = row.get("age")
            if age and int(age) >= min_age:
                _master_table.append(row)

        master_table = _master_table

    if max_age:
        _master_table = []
        for row in master_table:
            age = row.get("age")
            if age and int(age) <= max_age:
                _master_table.append(row)

        master_table = _master_table

    if min_market_value:
        _master_table = []
        for row in master_table:
            mv = utils.convert_price_string(row["market_value"])
            if mv and int(mv) >= min_market_value:
                _master_table.append(row)

        master_table = _master_table

    if max_market_value:
        _master_table = []
        for row in master_table:
            mv = utils.convert_price_string(row["market_value"])
            if mv and int(mv) <= max_market_value:
                _master_table.append(row)

        master_table = _master_table

    if min_totw:
        _master_table = []
        for row in master_table:
            totw_count = row.get("totw_count")
            if totw_count and int(totw_count) >= min_totw:
                _master_table.append(row)

        master_table = _master_table

    if max_totw:
        _master_table = []
        for row in master_table:
            totw_count = row.get("totw_count")
            if totw_count and int(totw_count) <= max_totw:
                _master_table.append(row)

        master_table = _master_table


    if not sort:
        print(format_display_table(sorted(master_table, key=lambda row: -int(row["totw_count"]))))
        print(format_display_table([{"count": len(master_table)}]))
        mv_mean = statistics.harmonic_mean([utils.convert_price_string(r["market_value"]) for r in master_table])
        print(mv_mean)


def get_price_string(p):
    if p >= 1000000000:
        return f"€{round(float(p/1000000000), 1)}B"
    if 1000000 < p <= 1000000000:
        return f"€{round(float(p/1000000), 1)}M"
    if 1000 < p <= 1000000:
        return f"€{round(float(p/1000))}K"


def get_transfer_row(t):
    on_loan = t["onLoan"]
    fee = t["fee"] or {}
    fee_value = fee.get("value")
    name = t["name"]
    player_id = t["playerId"]
    date = t["transferDate"]
    position = t.get("position") or {}
    position = position.get("label")
    from_club = t["fromClub"]
    to_club = t["toClub"]
    market_value = t.get("marketValue")
    return {
        "name": name,
        "id": player_id,
        "date": str(datetime.fromisoformat(date).date()),
        "position": position,
        "from_club": from_club,
        "to_club": to_club,
        "market_value": market_value,
        "fee": fee_value,
        "on_loan": on_loan
    }


def print_header(h, space_length=5, char="=", side_char="||"):
    spaces = " " * space_length
    header = f"{side_char}{spaces}{h}{spaces}{side_char}"
    header_banner = char * len(header)
    print("\n".join([header_banner, header, header_banner]))
    print("\n")


def print_table(table, header=None, field_names=None):
    if header:
        print_header(header)

    print(format_display_table(table, field_names=field_names))
    print("\n")


@cli.command
@click.argument("league_id", required=True, type=click.INT)
@click.option("-d", "--display", type=click.BOOL, default=True)
@click.option("-i", "--transfers-in", type=click.BOOL, default=True)
@click.option("-o", "--transfers-out", type=click.BOOL, default=False)
@click.option("-f", "--ignore-no-fee", type=click.BOOL, default=True)
def get_league_transfer_list(league_id, display, transfers_in, transfers_out, ignore_no_fee):
    year = datetime.today().year
    transfers = None
    path = f"data/transfers/{league_id}/{year}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            transfers = json.load(f)

    if not transfers:
        league = api.get_league(league_id)
        team_ids = [t["id"] for t in league["table"][0]["data"]["table"]["all"]]
        transfers = {"players_in": [], "players_out": []}
        for t in team_ids:
            team = api.get_team(t)
            if team:
                if team.get("transfers"):
                    players_in = [get_transfer_row(t) for t in team.get("transfers", {}).get("data", {}).get("Players in", [])]
                    players_out = [get_transfer_row(t) for t in team.get("transfers", {}).get("data", {}).get("Players out", [])]
                    if players_in:
                        transfers["players_in"].extend(players_in)
                    if players_out:
                        transfers["players_out"].extend(players_out)    

    if not os.path.exists(path):
        os.makedirs(os.path.split(path)[0], exist_ok=True)
        with open(path, "w") as f:
            json.dump(transfers, f)
    
    if display:
        sums_table = []
        if transfers_in:
            print_header("TRANSFERS IN", space_length=60, char="-", side_char="|")
            grouped = {key: list(group) for key, group in groupby(transfers["players_in"], key=lambda t: t["to_club"])}
            sums = []
            for team in grouped:
                print_header(team, space_length=(50 - 4 - len(team)))
                team_transfers = grouped[team]
                for t in team_transfers:
                    del t["to_club"]
                with_fee = [t for t in team_transfers if t["fee"]]
                without_fee = [t for t in team_transfers if not t["fee"]]
                if with_fee:
                    for t in with_fee:
                        try:
                            if not t["on_loan"]:
                                fee_v = utils.convert_price_string(t["fee"])
                                mv_v = utils.convert_price_string(t["market_value"])
                                t["fee_mv_ratio"] = round(fee_v/mv_v,2)
                        except:
                            pass
                        finally:
                            if not t.get("fee_mv_ratio"):
                                t["fee_mv_ratio"] = "n/a"
                    
                    with_fee = sorted(with_fee, key=lambda t: -datetime.fromisoformat(t["date"]).timestamp())
                    print("With Fee")
                    print_table(with_fee, field_names=["Name", "Id", "Date", "P", "From", "MV", "F", "On Loan", "F/MV"])
                    #print(format_display_table(sorted(with_fee, key=lambda t: -datetime.fromisoformat(t["date"]).timestamp())))
                    total_spend = sum([int(utils.convert_price_string(t["fee"])) for t in with_fee])
                    sums.append({"team": team, "total_spend": total_spend})
                    sums = sorted(sums, key=lambda d: -d["total_spend"])

                if without_fee:
                    for t in without_fee:
                        del t["fee"]

                    free_agents = [t for t in without_fee if t["from_club"] == "Free agent"]
                    not_free_agents = [t for t in without_fee if t["from_club"] != "Free agent"]
                    not_free_agents = sorted(not_free_agents, key=lambda t: -datetime.fromisoformat(t["date"]).timestamp())
                    print("Without Fee")
                    print_table(not_free_agents, field_names=["Name", "Id", "Date", "P", "From", "MV", "On Loan"])
                    if free_agents:
                        for t in free_agents:
                            del t["from_club"]
                        free_agents = sorted(free_agents, key=lambda t: -datetime.fromisoformat(t["date"]).timestamp())
                        print("Free Agent(s)")
                        print_table(free_agents, field_names=["Name", "Id", "Date", "P", "MV", "On Loan"])

                sums_table = [{"team": s["team"], "total_spend": get_price_string(s["total_spend"])} for s in sums]

        print_header("STATS")
        print(format_display_table(sums_table))
        
        
if __name__ == "__main__":
    cli()

from api import save_league_totw_season_data
from utils import convert_camel_to_snake

from operator import itemgetter

from loguru import logger
from prettytable import PrettyTable
import click

def format_display_table(items, keys=[]):
    table = PrettyTable()
    if not keys:
        keys = items[0].keys()

    table.field_names = [convert_camel_to_snake(key) for key in keys]
    for i in items:
        table.add_row(itemgetter(*keys)(i))

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
        print(f"Week {team['round']}")
        players = team["players"]
        keys = ["name", "participantId", "matchId", "rating", "motm"]
        player_table = format_display_table(players, keys=keys)
        print(player_table)


if __name__ == "__main__":
    cli()
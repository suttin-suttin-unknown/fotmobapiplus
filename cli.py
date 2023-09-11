from api import save_league_totw_season_data

from loguru import logger
import click



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
    logger.info(f"TOTW Data - League: {league_id} - Year: {season_year}: {data}")


if __name__ == "__main__":
    cli()
from loguru import logger
from tinydb import TinyDB, Query

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
    
    def get_players_table(self):
        return self.db.table("players")
    
    def get_player(self, player_id):
        return self.get_players_table().get(Query().id == player_id)
    
    # def get_league(self, league_id):
    #     table = self.db.table("leagues")
    #     league = table.get(Query().id == league_id)
    #     return league

    # def upsert_player(self, player, debug=False):
    #     player_id = player["id"]
    #     existing_player = self.get_player(player_id)
    #     table = self.db.table("players")
    #     if existing_player:    
    #         if debug:
    #             logger.debug(f"Player {player_id} exists. Updating.")
    #         table.update(player, Query().id == player_id)
    #     else:
    #         table.insert(player)

    # def upsert_league(self, league, debug=False):
    #     league_id = league["id"]
    #     existing_league = self.get_league(league_id)
    #     table = self.db.table("leagues")
    #     if existing_league:
    #         if debug:
    #             logger.debug(f"League {league_id} exists. Updating.")
    #         table.update(league, Query().id == league_id)
    #     else:
    #         table.insert(league)
from loguru import logger
from tinydb import TinyDB, Query

class FotmobDB:
    _instance = None

    def __new__(cls, db_file="fotmob.json"):
        if cls._instance is None:
            cls._instance = super(FotmobDB, cls).__new__(cls)
            cls._instance.db = TinyDB(db_file)
        return cls._instance
    
    def upsert_player(self, player, debug=False):
        player_id = player["id"]
        player_query = Query()
        table = self.db.table("players")
        current_data = table.get(player_query.id == player_id)
        if current_data:
            if debug:
                logger.debug(f"Player {player_id} exists. Updating.")
            table.update(player, player_query.id == player_id)
        else:
            table.insert(player)


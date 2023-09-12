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
    

if __name__ == "__main__":
    db = FotmobDB()
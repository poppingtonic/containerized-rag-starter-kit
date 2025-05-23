import psycopg2
from psycopg2.extras import RealDictCursor
from .config import Config

def get_db_connection():
    return psycopg2.connect(Config.DB_URL, cursor_factory=RealDictCursor)
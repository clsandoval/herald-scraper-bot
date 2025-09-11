import os
import logging
from dotenv import load_dotenv

from supabase import create_client, Client
from typing import Dict, Any, Optional

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.warning("SUPABASE_URL or SUPABASE_KEY environment variables not set")
    supabase: Optional[Client] = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def insert_row(table_name: str, data: Dict[str, Any]) -> bool:
    """
    Insert a row into the specified Supabase table.

    Args:
        table_name (str): Name of the table to insert into
        data (Dict[str, Any]): Dictionary containing the row data to insert

    Returns:
        bool: True if insertion was successful, False otherwise

    Example:
        success = insert_row("matches", {
            "match_id": 12345,
            "duration": 2400,
            "kill_density": 1.8,
            "date": "2024-01-01 12:00:00"
        })
    """
    if not supabase:
        logging.error("Supabase client not initialized. Check environment variables.")
        return False

    try:
        result = supabase.table(table_name).insert(data).execute()
        logging.info(f"Successfully inserted row into {table_name}: {result.data}")
        return True
    except Exception as e:
        logging.error(f"Failed to insert row into {table_name}: {str(e)}")
        return False

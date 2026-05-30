import os
import psycopg2
from dotenv import load_dotenv
from nba_api.stats.endpoints import leaguedashplayerstats

load_dotenv()

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS player_stats (
    id SERIAL PRIMARY KEY,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    points_per_game NUMERIC(5, 2),
    assists_per_game NUMERIC(5, 2),
    rebounds_per_game NUMERIC(5, 2),
    games_played INTEGER
);
"""

UPSERT_ROW = """
INSERT INTO player_stats (player_name, team, points_per_game, assists_per_game, rebounds_per_game, games_played)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING;
"""


def fetch_player_stats():
    print("Fetching 2023-24 player stats from NBA API...")
    response = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2023-24",
        per_mode_detailed="PerGame",
    )
    df = response.get_data_frames()[0]
    return df[["PLAYER_NAME", "TEAM_ABBREVIATION", "PTS", "AST", "REB", "GP"]]


def load_into_db(df):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in .env")

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE)
                rows = [
                    (
                        row["PLAYER_NAME"],
                        row["TEAM_ABBREVIATION"],
                        round(float(row["PTS"]), 2),
                        round(float(row["AST"]), 2),
                        round(float(row["REB"]), 2),
                        int(row["GP"]),
                    )
                    for _, row in df.iterrows()
                ]
                cur.executemany(UPSERT_ROW, rows)
                print(f"Inserted {len(rows)} player records into player_stats.")
    finally:
        conn.close()


if __name__ == "__main__":
    df = fetch_player_stats()
    load_into_db(df)

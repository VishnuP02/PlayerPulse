from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pathlib import Path

app = FastAPI(title="PlayerPulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

PRIMARY_FILE = DATA_DIR / "mlb_players.csv"
SECONDARY_FILE = DATA_DIR / "mlb_2025_players.csv"


def load_and_normalize_csv(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(file_path)

    rename_map = {
        "Name": "Player",
        "Tm": "Team",
        "AVG": "BA",
    }
    df = df.rename(columns=rename_map)

    if "Year" not in df.columns and "2025" in file_path.name:
        df["Year"] = 2025

    required_columns = ["Player", "Team", "Year", "G", "HR", "RBI", "BA", "OBP", "SLG", "OPS", "WAR"]

    for col in required_columns:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[required_columns].copy()

    df["Player"] = df["Player"].astype(str).str.strip()
    df["Team"] = df["Team"].astype(str).str.strip()

    numeric_cols = ["Year", "G", "HR", "RBI", "BA", "OBP", "SLG", "OPS", "WAR"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Player", "Year"])
    return df


frames = []

if PRIMARY_FILE.exists():
    frames.append(load_and_normalize_csv(PRIMARY_FILE))

if SECONDARY_FILE.exists():
    frames.append(load_and_normalize_csv(SECONDARY_FILE))

if not frames:
    raise FileNotFoundError("No dataset files found in the data folder.")

df = pd.concat(frames, ignore_index=True)

df = df.drop_duplicates(
    subset=["Player", "Team", "Year", "G", "HR", "RBI", "BA", "OBP", "SLG", "OPS", "WAR"]
)


@app.get("/")
def home():
    return {"message": "Welcome to PlayerPulse API"}


@app.get("/players")
def get_players():
    players = sorted(df["Player"].dropna().unique().tolist())
    return {"players": players}


@app.get("/player/{player_name}")
def get_player_stats(player_name: str):
    player_df = df[df["Player"].str.lower() == player_name.lower()].sort_values("Year")

    if player_df.empty:
        return {"error": f"No data found for {player_name}"}

    return {
        "player": player_name,
        "stats": player_df.to_dict(orient="records")
    }


@app.get("/compare")
def compare_players(player1: str, player2: str):
    p1 = df[df["Player"].str.lower() == player1.lower()].sort_values("Year")
    p2 = df[df["Player"].str.lower() == player2.lower()].sort_values("Year")

    if p1.empty or p2.empty:
        return {"error": "One or both players not found"}

    return {
        "player1": player1,
        "player1_stats": p1.to_dict(orient="records"),
        "player2": player2,
        "player2_stats": p2.to_dict(orient="records")
    }


@app.get("/top")
def top_players(stat: str = "HR", year: int = 2024, limit: int = 10):
    valid_stats = ["HR", "RBI", "BA", "OBP", "SLG", "OPS", "WAR", "G"]

    if stat not in valid_stats:
        return {"error": f"Invalid stat. Choose from: {valid_stats}"}

    year_df = df[df["Year"] == year].copy()

    if year_df.empty:
        return {"error": f"No data found for year {year}"}

    top_df = year_df.sort_values(stat, ascending=False).head(limit)

    return {
        "year": year,
        "stat": stat,
        "leaders": top_df[["Player", "Team", "Year", stat]].to_dict(orient="records")
    }
import pandas as pd
import re

def clean_commercial_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    name_corrections = {
        "Pedro Bruges": "Pedro Luis Bruges",
        "pedro bruges": "Pedro Luis Bruges",
        "": "Andrés Consuegra"
    }
    if 'commercial' in df.columns:
        df['commercial'] = df['commercial'].astype(str).str.strip()
        df['commercial'] = df['commercial'].replace(name_corrections)
    return df


def clean_request_id(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if 'REQUEST_ID' in df.columns:
        df = df.rename(columns={'REQUEST_ID': 'request_id'})
    df.columns = df.columns.str.strip().str.lower()

    if 'request_id' in df.columns:
        df['request_id'] = df['request_id'].astype(str).str.extract(r"(Q\d{1,})", expand=False)
    return df


def preprocess_data(df_requested, df_ground, df_feedback):

    df_requested = clean_request_id(df_requested)
    df_ground = clean_request_id(df_ground)
    df_feedback = clean_request_id(df_feedback)

    if "time" in df_requested.columns:
        df_requested["time"] = pd.to_datetime(df_requested["time"], dayfirst=True, errors="coerce")

    if "time" in df_ground.columns:
        df_ground["time"] = pd.to_datetime(df_ground["time"], errors="coerce")

    if "time" in df_feedback.columns:
        df_feedback["time"] = pd.to_datetime(df_feedback["time"], errors="coerce")

    ids_requested = set(df_requested["request_id"].dropna())
    df_ground_unique = df_ground[~df_ground["request_id"].isin(ids_requested)]
    df_all_requests = pd.concat([df_requested, df_ground_unique], ignore_index=True)

    df = df_all_requests.merge(df_feedback, on="request_id", how="left", suffixes=("", "_feedback"))

    if "assignaton status" in df.columns:
        df["assignaton status"] = df["assignaton status"].astype(str).str.strip().str.lower()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str)

    if "assigned_to" in df.columns:
        df = df[~df["assigned_to"].str.contains("shadia", case=False, na=False)]

    return df

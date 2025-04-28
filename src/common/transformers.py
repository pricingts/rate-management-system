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


def convert_time_columns(df, dayfirst=False):
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], format="mixed", dayfirst=dayfirst, errors="coerce")
    return df

def merge_requested_and_ground(df_requested, df_ground):
    ids_requested = set(df_requested["request_id"].dropna())
    df_ground_unique = df_ground[~df_ground["request_id"].isin(ids_requested)]
    df_all_requests = pd.concat([df_requested, df_ground_unique], ignore_index=True)
    return df_all_requests

def merge_with_feedback(df_all_requests, df_feedback):
    return df_all_requests.merge(df_feedback, on="request_id", how="left", suffixes=("", "_feedback"))

def clean_assignation_status(df):
    if "assignaton status" in df.columns:
        df["assignaton status"] = df["assignaton status"].astype(str).str.strip().str.lower()
    return df

def ensure_all_columns_are_strings(df):
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str)
    return df

def remove_specific_assignees(df, names_to_remove):
    if "assigned_to" in df.columns:
        pattern = '|'.join(names_to_remove)
        df = df[~df["assigned_to"].str.contains(pattern, case=False, na=False)]
    return df

def preprocess_data(df_requested, df_ground, df_feedback):

    df_requested = clean_request_id(df_requested)
    df_ground = clean_request_id(df_ground)
    df_feedback = clean_request_id(df_feedback)

    df_requested = convert_time_columns(df_requested, dayfirst=True)
    df_ground = convert_time_columns(df_ground)
    df_feedback = convert_time_columns(df_feedback)

    df_all_requests = merge_requested_and_ground(df_requested, df_ground)
    df = merge_with_feedback(df_all_requests, df_feedback)

    df = clean_assignation_status(df)
    df = ensure_all_columns_are_strings(df)
    df = remove_specific_assignees(df, ["shadia"])

    return df

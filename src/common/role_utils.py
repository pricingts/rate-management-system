# src/common/role_utils.py
import pandas as pd
from typing import Tuple, Dict
from ..config import SHEETS
from .google_sheets import load_all_records

def load_dataframes_for(role: str) -> Dict[str, pd.DataFrame]:
    dfs: Dict[str, pd.DataFrame] = {}
    if role in ("commercial", "pricing", "admin"):
        dfs["request"]  = load_all_records(*SHEETS["all_quotes"])
        dfs["contracts"] = load_all_records(*SHEETS["contracts"])
    if role in ("ground", "admin"):
        dfs["ground"]   = load_all_records(*SHEETS["ground_quotations"])
    return {k: dfs.get(k, pd.DataFrame()) for k in ("request", "contracts", "ground")}

def filter_commercial(
    req: pd.DataFrame, ctr: pd.DataFrame, grd: pd.DataFrame,
    user_name: str, user_email: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df_req = req[req["COMMERCIAL"] == user_name]
    df_ctr = ctr[ctr["COMMERCIAL"] == user_name]
    return df_req, df_ctr, pd.DataFrame()

def filter_pricing(
    req: pd.DataFrame, ctr: pd.DataFrame, grd: pd.DataFrame,
    user_name: str, user_email: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    name_map = {
        'customer9@tradingsolutions.com': 'Luis',
        'pricing11@tradingsolutions.com': 'Esthefy',
        'pricing6@tradingsolutions.com': 'Heidi',
        'pricing8@tradingsolutions.com': 'Mafe'
    }
    df_req = req
    if user_email in name_map:
        target = name_map[user_email]
        mask = df_req["ASSIGNED_TO"].fillna("").apply(
            lambda s: target in [e.strip() for e in s.split(",")]
        )
        df_req = df_req[mask]
    return df_req, ctr, pd.DataFrame()

def filter_ground(
    req: pd.DataFrame, ctr: pd.DataFrame, grd: pd.DataFrame,
    user_name: str, user_email: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Para ground usamos la pestaña “Ground Quotations” como request
    return grd, pd.DataFrame(), pd.DataFrame()

def filter_admin(
    req: pd.DataFrame, ctr: pd.DataFrame, grd: pd.DataFrame,
    user_name: str, user_email: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return req, ctr, grd

FILTERS = {
    "commercial": filter_commercial,
    "pricing":    filter_pricing,
    "ground":     filter_ground,
    "admin":      filter_admin,
}

def get_role_dfs(
    role: str, user_name: str, user_email: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = load_dataframes_for(role)
    fn = FILTERS.get(role, lambda r, c, g, n, e: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()))
    return fn(raw["request"], raw["contracts"], raw["ground"], user_name, user_email)

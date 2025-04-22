import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

@st.cache_resource(ttl=100000)
def get_gsheet_client() -> gspread.Client:
    creds_info = st.secrets["google_sheets_credentials"]
    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=1800)
def load_data_from_sheets(secret_key: str, worksheet_name: str) -> pd.DataFrame:
    try:
        sheet_id = st.secrets["general"][secret_key]
        client = get_gsheet_client()
        worksheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error cargando '{worksheet_name}': {e}")
        return pd.DataFrame()
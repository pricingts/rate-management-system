import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from src.services.dashboard_utils import *

def show(role):
    df_requested = load_data_from_sheets("quotations_requested", "All Quotes")
    df_contracts = load_data_from_sheets("costs_sales_contracts", "CONTRATOS")
    df_feedback = load_data_from_sheets("time_sheet_id", "Quotations Feedback")

    for df in (df_requested, df_contracts, df_feedback):
        if "REQUEST_ID" in df.columns:
            df.rename(columns={"REQUEST_ID": "request_id"}, inplace=True)
        # opcional: uniformizar minúsculas/trim
        df.columns = df.columns.str.strip().str.lower()

    # 1) Uno df_requested con df_feedback por request_id
    df_merged = df_requested.merge(
        df_feedback,
        on="request_id",
        how="left",
        suffixes=("", "_feedback")
    )

    # 2) Al resultado le uno df_contracts
    df_merged = df_merged.merge(
        df_contracts,
        on="request_id",
        how="left",
        suffixes=("", "_contract")
    )

    # Y muestro el resultado
    st.dataframe(df_merged)

    # st.write(df_requested)
    # st.write(df_contracts)
    # st.write(df_assigment)

import streamlit as st
import pandas as pd
import numpy as np
from src.services.dashboard_utils import *
import plotly.graph_objects as go

def show(role, user):
    df_requested, df_contracts, df_feedback = load_all_data()
    df = preprocess_data(df_requested, df_contracts, df_feedback)
    df = clean_commercial_names(df)

    if role == "commercial":
        df = df[df["commercial"].str.lower().str.strip() == user.lower().strip()]

    df = apply_filters(df, role)

    if df.empty:
        st.warning("No data to display with the current filters.")
        return

    show_kpis(df)

    col1, col2 = st.columns(2)
    with col1:
        plot_evolution(df)

    with col2:
        plot_assignation_status_pie(df)
    
    col3, col4 = st.columns(2)
    with col3:
        plot_unassignment_reasons(df)
    
    with col4:
        plot_price_comparison(df)
    
    col5, col6 = st.columns(2)
    with col5:
        plot_top_clients_requests(df)
    with col6:
        plot_assigned_requests_by_person(df)

    #st.write(df)
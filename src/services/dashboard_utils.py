import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go
import plotly.express as px
import re


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

def load_all_data():
    df_requested = load_data_from_sheets("quotations_requested", "All Quotes")
    df_feedback = load_data_from_sheets("time_sheet_id", "Quotations Feedback")
    return df_requested, df_feedback

def clean_commercial_names(df):
    name_corrections = {
        "Pedro Bruges": "Pedro Luis Bruges",
        "pedro bruges": "Pedro Luis Bruges",  
        "": "Andrés Consuegra"
    }
    df["commercial"] = df["commercial"].astype(str).str.strip()
    df["commercial"] = df["commercial"].replace(name_corrections)
    return df

def preprocess_data(df_requested, df_feedback):
    def clean_request_id(df):
        if "REQUEST_ID" in df.columns:
            df.rename(columns={"REQUEST_ID": "request_id"}, inplace=True)
        df.columns = df.columns.str.strip().str.lower()
        if "request_id" in df.columns:
            df["request_id"] = df["request_id"].astype(str).str.extract(r"(Q\d+)", expand=False)
        return df

    df_requested = clean_request_id(df_requested)
    df_feedback = clean_request_id(df_feedback)

    df = df_requested.merge(df_feedback, on="request_id", how="left", suffixes=("", "_feedback"))

    if "assignaton status" in df.columns:
        df["assignaton status"] = df["assignaton status"].astype(str).str.strip().str.lower()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str)
    
    if "assigned_to" in df.columns:
        df = df[~df["assigned_to"].str.contains("shadia", case=False, na=False)]

    return df

def extract_ports(df):
    def get_origin_and_destinations(route_str):
        if not isinstance(route_str, str) or not route_str:
            return ("", "")
        ports = re.findall(r"\(([^)]+)\)", route_str)
        if not ports:
            return ("", "")
        origin = ports[0]
        destinations = list(set(ports[1:]))  # quitar duplicados
        return origin, ", ".join(destinations)

    df["routes_info"] = df["routes_info"].fillna("")
    extracted = df["routes_info"].map(get_origin_and_destinations)

    if extracted.isnull().any() or extracted.empty:
        df["origin_port"] = ""
        df["destination_ports"] = ""
    else:
        df["origin_port"], df["destination_ports"] = zip(*extracted)

    return df


def apply_filters(df, role):
    if "origin_port" not in df.columns or "destination_ports" not in df.columns:
        df = extract_ports(df)

    df_filtered = df.copy()

    client_filter = []
    assigned_filter = []
    status_filter = []
    origin_filter = []
    destination_filter = []

    col1, col2, col3 = st.columns(3)

    with col1:
        client_filter = st.multiselect("Client", sorted(df_filtered["client"].dropna().unique()))
        if client_filter:
            df_filtered = df_filtered[df_filtered["client"].isin(client_filter)]

    with col2:
        assigned_split = df_filtered["assigned_to"].dropna().astype(str).str.split(r",\s*")
        assigned_flat = sorted(set(name.strip() for sublist in assigned_split for name in sublist))

        assigned_filter = st.multiselect("Pricing Member", assigned_flat)
        if assigned_filter:
            df_filtered = df_filtered[df_filtered["assigned_to"].apply(
                lambda val: any(name in str(val) for name in assigned_filter)
            )]

    with col3:
        status_filter = st.multiselect("Assignation Status", sorted(df_filtered["assignaton status"].dropna().unique()))
        if status_filter:
            df_filtered = df_filtered[df_filtered["assignaton status"].isin(status_filter)]

    if role == "admin":
        col4, col5, col6 = st.columns(3)
    else:
        col4, col5 = st.columns(2)
        col6 = None

    with col4:
        origin_filter = st.multiselect("Port of Origin", sorted(df_filtered["origin_port"].dropna().unique()))
        if origin_filter:
            df_filtered = df_filtered[df_filtered["origin_port"].isin(origin_filter)]

    with col5:
        all_destinations = sorted(set(", ".join(df_filtered["destination_ports"]).split(", ")))
        destination_filter = st.multiselect("Port of Destination", all_destinations)
        if destination_filter:
            df_filtered = df_filtered[df_filtered["destination_ports"].apply(
                lambda x: any(dest in x for dest in destination_filter)
            )]

    if role == "admin" and col6:
        with col6:
            all_commercials = sorted(df["commercial"].dropna().unique())
            all_commercials_display = ["-- All --"] + all_commercials
            selected_commercial = st.selectbox("Commercial", all_commercials_display)
            if selected_commercial != "-- All --":
                df_filtered = df_filtered[df_filtered["commercial"] == selected_commercial]

    return df_filtered


def show_kpis(df):
    total_requests = len(df)
    total_assigned = df["assignaton status"].eq("yes").sum()
    total_not_assigned = df["assignaton status"].eq("no").sum()
    assignment_rate = (total_assigned / total_requests * 100) if total_requests > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests", total_requests)
    col2.metric("Assigned", total_assigned)
    col3.metric("Not Assigned", total_not_assigned)
    col4.metric("Assignment Rate", f"{assignment_rate:.1f}%")

def plot_evolution(df):
    df["request_date"] = pd.to_datetime(df["time"], dayfirst=True, errors="coerce")
    df["assigned_date"] = pd.to_datetime(df["time_feedback"], dayfirst=True, errors="coerce")
    df["request_month"] = df["request_date"].dt.to_period("M").astype(str)
    df["assigned_month"] = df["assigned_date"].dt.to_period("M").astype(str)

    reqs = df.groupby("request_month").agg(total_requests=("request_id", "count")).reset_index().rename(columns={"request_month": "month"})
    assigns = df[df["assignaton status"] == "yes"].groupby("assigned_month").agg(assigned=("request_id", "count")).reset_index().rename(columns={"assigned_month": "month"})

    evol = pd.merge(reqs, assigns, on="month", how="outer").fillna(0)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=evol["month"], y=evol["total_requests"],
        name="Total Requests",
        mode="lines+markers",
        line=dict(color="#276CF1"),
        hovertemplate='Month: %{x}<br>Total Requests: %{y}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=evol["month"], y=evol["assigned"],
        name="Assigned",
        mode="lines+markers",
        line=dict(color="#212121"), 
        hovertemplate='Month: %{x}<br>Assigned: %{y}<extra></extra>'
    ))

    fig.update_layout(
        title="Request Evolution Over Time",
        xaxis_title="Month",
        yaxis_title="Requests",
        hovermode="x unified",
        height=400, 
        margin=dict(t=40, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=0.95,
            xanchor="center",
            x=0.5
        )
    )

    st.plotly_chart(fig)


def plot_unassignment_reasons(df):
    df["assignaton status"] = df["assignaton status"].astype(str).str.strip().str.lower()
    df["reason_unassigned"] = df["reason"].astype(str).str.strip()

    df_unassigned = df[df["assignaton status"] == "no"]

    if df_unassigned.empty:
        st.info("No unassigned records to display reasons.")
        return

    reasons = df_unassigned["reason_unassigned"].value_counts().reset_index()
    reasons.columns = ["reason", "count"]

    blue_palette = ["#276CF1", "#4E8CF4", "#75ADF8", "#88BDF9", "#9BCDFB", "#AFDEFD"]

    fig = go.Figure(go.Pie(
        labels=reasons["reason"],
        values=reasons["count"],
        hole=0.5,
        textinfo='label+percent',
        textposition='outside',
        hoverinfo='label+value',
        marker=dict(colors=blue_palette[:len(reasons)])
    ))

    fig.update_layout(
        title="Reasons for Not Assigned",
        showlegend=False,
        height=430
    )

    st.plotly_chart(fig)

def plot_top_clients_requests(df):
    top_clients = df["client"].value_counts().head(10).index.tolist()
    df_top = df[df["client"].isin(top_clients)].copy()

    df_top["assignaton status"] = df_top["assignaton status"].astype(str).str.strip().str.lower()

    total = df_top.groupby("client").size().reset_index(name="Total Requests")
    assigned = df_top[df_top["assignaton status"] == "yes"].groupby("client").size().reset_index(name="Assigned Requests")

    merged = pd.merge(total, assigned, on="client", how="left").fillna(0)
    merged = merged.sort_values(by="Total Requests", ascending=False)

    # Abreviar nombres largos
    merged["short_client"] = merged["client"].apply(lambda x: x[:25] + "..." if len(x) > 28 else x)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=merged["short_client"],
        y=merged["Total Requests"],
        name="Total Requests",
        marker_color="#276CF1",
        hovertext=merged["client"],
        text=merged["Total Requests"],
        textposition="inside",  # 👈 etiquetas arriba
        texttemplate="%{text:.0f}"
    ))

    fig.add_trace(go.Bar(
        x=merged["short_client"],
        y=merged["Assigned Requests"],
        name="Assigned Requests",
        marker_color="#212121",
        hovertext=merged["client"],
        text=merged["Assigned Requests"],
        textposition="inside",  # 👈 etiquetas arriba
        texttemplate="%{text:.0f}"
    ))

    fig.update_layout(
        title="Top 10 Clients by Requests and Assigned",
        xaxis_title="Client",
        yaxis_title="Requests",
        barmode="group",
        height=450,
        margin=dict(t=80, b=100),
        xaxis_tickangle=-30,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1,
            xanchor="center",
            x=0.5
        )
    )

    st.plotly_chart(fig, use_container_width=True)



def plot_price_comparison(df):
    df["assignaton status"] = df["assignaton status"].astype(str).str.strip().str.lower()
    df["reason"] = df["reason"].astype(str).str.strip().str.lower()

    df_filtered = df[
    (df["assignaton status"] == "no") &
    (df["reason"].str.contains("uncompetitive prices"))
    ].copy()

    if df_filtered.empty:
        st.info("No unassigned requests due to uncompetitive prices.")
        return

    df_filtered["cost"] = pd.to_numeric(df_filtered["cost"], errors="coerce")
    df_filtered["target"] = pd.to_numeric(df_filtered["target"], errors="coerce")
    df_filtered.dropna(subset=["cost", "target"], inplace=True)

    df_filtered["diff"] = df_filtered["target"] - df_filtered["cost"]
    df_filtered.sort_values("diff", ascending=False, inplace=True)

    fig = go.Figure(data=[
        go.Bar(
            name='Cost',
            x=df_filtered["request_id"],
            y=df_filtered["cost"],
            text=df_filtered["cost"],
            texttemplate='$%{text:,.0f}',
            textposition='inside',  # 👈 dentro de la barra
            marker_color='#276CF1'
        ),
        go.Bar(
            name='Target',
            x=df_filtered["request_id"],
            y=df_filtered["target"],
            text=df_filtered["target"],
            texttemplate='$%{text:,.0f}',
            textposition='inside',  # 👈 dentro también
            marker_color='#212121'
        )
    ])

    fig.update_layout(
        barmode='group',
        bargap=0.5,  # 👈 separación entre grupos
        title="Cost vs Target Comparison - Unassigned Requests (Price Reason)",
        xaxis_title="Request ID",
        yaxis_title="Price (USD)",
        height=450,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1,
            xanchor="center",
            x=0.5
        )
    )

    st.plotly_chart(fig, use_container_width=True)

def plot_assigned_requests_by_person(df):
    if "assigned_to" not in df.columns or df["assigned_to"].dropna().empty:
        st.info("No data available in 'assigned_to' to plot.")
        return

    assigned_series = df["assigned_to"].dropna().astype(str).str.split(r",\s*")  # corregido con raw string
    all_assigned = [name.strip() for sublist in assigned_series for name in sublist]

    if not all_assigned:
        st.info("No assignments found to display.")
        return

    assigned_counts = pd.Series(all_assigned).value_counts().reset_index()
    assigned_counts.columns = ["Pricing", "Requests"]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=assigned_counts["Pricing"],
        y=assigned_counts["Requests"],
        marker_color="#276CF1",
        text=assigned_counts["Requests"],
        textposition="inside", 
        texttemplate="%{text}", 
        hoverinfo="x+y"
    ))

    fig.update_layout(
        title="Pricing Team Workload Distribution",
        xaxis_title="Pricing Member",
        yaxis_title="Requests",
        height=450,
        margin=dict(t=60, b=80),
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_assignation_status_pie(df):
    if "assignaton status" not in df.columns:
        st.warning("The column 'assignaton status' is missing.")
        return

    df["assignaton status"] = df["assignaton status"].astype(str).str.strip().str.lower()
    df["assignaton status"] = df["assignaton status"].replace("nan", "n/a")

    status_counts = df["assignaton status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]

    color_map = {
        "yes": "#276CF1",    
        "no": "#212121",     
        "n/a": "#CCCCCC"  
    }
    colors = [color_map.get(s.lower(), "#999999") for s in status_counts["status"]]

    labels = [s.upper() for s in status_counts["status"]]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=status_counts["count"],
        hole=0,
        textinfo="label+percent",
        textposition="outside",
        hoverinfo="label+value",
        marker=dict(colors=colors)
    ))

    fig.update_layout(
        title="Assignation Status",
        showlegend=False,
        height=430
    )

    st.plotly_chart(fig, use_container_width=True)





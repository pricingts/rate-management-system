import streamlit as st
import pandas as pd
import re
from st_aggrid import AgGrid, GridOptionsBuilder
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

def list_contains(field_str, selections):
    if isinstance(field_str, list):
        return any(item in field_str for item in selections)
    items = re.split(r"[,\n;]+", str(field_str))
    items = [item.strip() for item in items if item.strip()]
    return any(s in items for s in selections)

def prepare_dataframe(df):
    if df.empty or "ROUTES_INFO" not in df.columns:
        return df

    # 3. Vectorizar extracción de origen y destino
    matches = df["ROUTES_INFO"].str.extractall(r"\(([^)]+)\)")
    matches.reset_index(inplace=True)
    # nivel 0: índice original, match: 0=origen, 1=destino
    origens = matches[matches["match"] == 0].set_index("level_0")[0]
    destinos = matches[matches["match"] == 1].set_index("level_0")[0]

    df["origen"] = df.index.to_series().apply(lambda i: [origens[i]] if i in origens.index else [])
    df["destino"] = df.index.to_series().apply(lambda i: [destinos[i]] if i in destinos.index else [])

    # Combinar transporte y modalidad
    df["TRANSPORT_COMBO"] = df.apply(
        lambda row: f"{row['TRANSPORT_TYPE']} - {row['MODALITY']}" 
                    if row['TRANSPORT_TYPE'] == "Maritime" else row['TRANSPORT_TYPE'], axis=1
    )

    # 5. Preprocesar columnas multi-valor en listas
    df["SERVICES_LIST"] = df["SERVICE"].fillna("").apply(
        lambda x: [item.strip() for item in re.split(r"[,\n;]+", x) if item.strip()]
    )
    df["CONTAINERS_LIST"] = df["TYPE_CONTAINER"].fillna("").apply(
        lambda x: [item.strip() for item in re.split(r"[,\n;]+", x) if item.strip()]
    )

    return df


def create_filters(df_full, key_prefix):
    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    with col1:
        origen_options = sorted({o for lst in df_full["origen"] for o in (lst or [])})
        selected_origen = st.multiselect('**Port of Origin**', origen_options, key=f"{key_prefix}_origen")

    with col2:
        destino_options = sorted({d for lst in df_full["destino"] for d in (lst or [])})
        selected_destino = st.multiselect('**Port of Destination**', destino_options, key=f"{key_prefix}_destino")

    with col3:
        service_options = sorted({s for lst in df_full["SERVICES_LIST"] for s in lst})
        selected_service = st.multiselect('**Service Requested**', service_options, key=f"{key_prefix}_service")

    with col4:
        transport_options = sorted(df_full['TRANSPORT_COMBO'].dropna().unique())
        selected_transport = st.multiselect("**Transport/Modality**", transport_options, key=f"{key_prefix}_transport")

    with col5:
        container_options = sorted({c for lst in df_full["CONTAINERS_LIST"] for c in lst})
        selected_container = st.multiselect('**Container Type**', container_options, key=f"{key_prefix}_cont_type")

    with col6:
        client_options = sorted(df_full['CLIENT'].dropna().unique())
        selected_client = st.multiselect('**Client**', client_options, key=f"{key_prefix}_client")

    return selected_origen, selected_destino, selected_service, selected_transport, selected_container, selected_client

def apply_filters(df_full, selected_origen, selected_destino, selected_client, selected_service, selected_container, selected_transport):
    df_filtered = df_full.copy()

    if selected_origen:
        df_filtered = df_filtered[df_filtered["origen"].apply(lambda x: any(o in x for o in selected_origen))]
    if selected_destino:
        df_filtered = df_filtered[df_filtered["destino"].apply(lambda x: any(d in x for d in selected_destino))]
    if selected_client:
        df_filtered = df_filtered[df_filtered["CLIENT"].isin(selected_client)]
    if selected_service:
        df_filtered = df_filtered[df_filtered["SERVICE"].isin(selected_service)]
    if selected_container:
        def row_has_container(container_str, selected):
            splitted = [item.strip() for item in re.split(r'[,\n;]+', str(container_str)) if item.strip()]
            return any(cont in splitted for cont in selected)
        df_filtered = df_filtered[df_filtered["TYPE_CONTAINER"].apply(lambda x: row_has_container(x, selected_container))]
    if selected_transport:
        df_filtered = df_filtered[df_filtered["TRANSPORT_COMBO"].isin(selected_transport)]

    return df_filtered

def show_metrics(df_filtered):
    request_quantity = df_filtered.shape[0]
    counts = df_filtered["TRANSPORT_COMBO"].value_counts()
    maritime_fcl_count = counts.get("Maritime - FCL", 0)
    maritime_lcl_count = counts.get("Maritime - LCL", 0)
    air_count = counts.get("Air", 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Number of Request", value=request_quantity)
    col2.metric(label="Maritime - FCL", value=maritime_fcl_count)
    col3.metric(label="Maritime - LCL", value=maritime_lcl_count)
    col4.metric(label="Air", value=air_count)


def show_grid(df_filtered, source):
    if df_filtered.empty:
        st.info("No hay registros para mostrar.")
        return

    visible_columns = [
        "REQUEST_ID", "CLIENT", "ROUTES_INFO", "INCOTERM", 
        "COMMODITY", "TRANSPORT_TYPE", "MODALITY", "TYPE_CONTAINER"
    ]
    df_display = df_filtered[visible_columns].copy()

    ids = df_filtered["REQUEST_ID"].dropna().unique().tolist()
    options = ["-- Select a request --"] + ids

    key = f"select_{source}_id"
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state[key] = options[0]

    selected_id = st.selectbox(
        "Select a request to view details", options,
        key=key
    )

    if selected_id not in options:
        st.session_state[f"select_{source}_id"] = "-- Select a request --"
        return

    st.dataframe(df_display, use_container_width=True, height=400, hide_index=True)

    if selected_id and selected_id != "-- Select a request --":
        selected_row = df_filtered[df_filtered["REQUEST_ID"] == selected_id]
        if not selected_row.empty:
            handle_row_selection(selected_row.to_dict("records"), source)

def handle_row_selection(selected_rows, source):
    if not selected_rows:
        return

    record = selected_rows[0]
    selected_df = pd.DataFrame([record])

    exclude_columns = [
        "origen", "destino", "EMAIL_SENT", "FEEDBACK",
        "ASSIGNED_TO", "DEADLINE", "TRANSPORT_COMBO"
    ]
    cols_to_drop = [c for c in exclude_columns if c in selected_df.columns]
    selected_df.drop(columns=cols_to_drop, inplace=True)

    selected_df = selected_df.T.reset_index()
    selected_df.columns = ["Field", "Value"]

    selected_df["Value"] = selected_df["Value"].astype(str)
    selected_df = selected_df[selected_df["Value"].str.strip().astype(bool)]
    selected_df = selected_df[selected_df["Value"].str.lower() != "nan"]
    selected_df.dropna(subset=["Value"], inplace=True)

    selected_df.set_index("Field", inplace=True)

    reset_dialog_inputs()
    st.session_state.selected_requested_quotation = None
    st.session_state.selected_ground_quotation = None
    st.session_state.selected_contract = None

    if source == "requested":
        st.session_state.selected_requested_quotation = selected_df
    elif source == "ground":
        st.session_state.selected_ground_quotation = selected_df
    else:  # "contract"
        st.session_state.selected_contract = selected_df

    st.session_state.dialog_type = source
    st.session_state.open_dialog = True



def filter_contracts(df, selected_origin, selected_destination, selected_cargo, selected_client):
    df_filtered = df.copy()
    if selected_origin:
        df_filtered = df_filtered[df_filtered["POL"].apply(lambda x: any(o in x for o in selected_origin))]
    if selected_destination:
        df_filtered = df_filtered[df_filtered["POD"].apply(lambda x: any(o in x for o in selected_destination))]
    if selected_cargo:
        df_filtered = df_filtered[df_filtered["Cargo Types"].apply(lambda x: any(o in x for o in selected_cargo))]
    if selected_client:
        df_filtered = df_filtered[df_filtered["Cliente"].apply(lambda x: any(o in x for o in selected_client))]
    return df_filtered

def get_sheets_client():
    creds = Credentials.from_service_account_info(
        st.secrets["google_sheets_credentials"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)


def get_sheets_client():
    creds = Credentials.from_service_account_info(
        st.secrets["google_sheets_credentials"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)


def get_worksheet(sheet_name):
    client = get_sheets_client()
    spreadsheet_id = st.secrets["general"]["time_sheet_id"]
    sheet = client.open_by_key(spreadsheet_id)

    try:
        worksheet = sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="10")
        headers = ["TIME","REQUEST_ID", "COMMERCIAL", "QUOTATION TYPE", "ASSIGNATON STATUS", 
                "REASON", "OTHER REASON", "COST", "TARGET"]
        worksheet.append_row(headers)

    return worksheet


def clear_filters(key_prefix):
    for field in ["origen", "destino", "service", "transport", "cont_type", "client",
                "pol", "pod", "cargo"]: 
        key = f"{key_prefix}_{field}"
        st.session_state[key] = []


def initialize_filters(key_prefix):
    for field in ["origen", "destino", "service", "transport", "cont_type", "client"]:
        key = f"{key_prefix}_{field}"
        if key not in st.session_state:
            st.session_state[key] = []

def initialize_filters_contracts(key_prefix):
    for field in ["pol", "pod", "cargo", "client"]:
        key = f"{key_prefix}_{field}"
        if key not in st.session_state:
            st.session_state[key] = []

def is_feedback_sent(request_id):
    worksheet = get_worksheet("Quotations Feedback")
    records = worksheet.get_all_records()
    sent_ids = [str(row.get("REQUEST_ID", "")).strip() for row in records]
    return str(request_id).strip() in sent_ids

def save_feedback_to_sheets(feedback_data):
    try:
        worksheet = get_worksheet("Quotations Feedback")
        
        now = datetime.now()
        datetime_str = now.strftime("%Y-%m-%d %H:%M:%S")

        new_row = [
            datetime_str,
            feedback_data.get("request_id", ""),
            feedback_data.get("commercial", ""),
            feedback_data.get("type", ""),
            feedback_data.get("assigned_status", ""),
            feedback_data.get("reason", ""),
            feedback_data.get("other_reason", ""),
            feedback_data.get("cost", ""),
            feedback_data.get("target", "")
        ]

        worksheet.append_row(new_row)

        return True, "Information saved successfully!"

    except Exception as e:
        return False, f"Error saving feedback: {str(e)}"


def reset_dialog_inputs():
    for key in ["assigned_status", "reason", "other_reason", "cost", "target"]:
        st.session_state.pop(key, None)

def clear_selected_quotation():
    st.session_state.selected_requested_quotation = None
    st.session_state.selected_contract = None
    st.session_state.selected_ground_quotation = None
    st.session_state.dialog_type = None
    st.session_state.open_dialog = False
    reset_dialog_inputs()



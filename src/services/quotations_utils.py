import streamlit as st
import pandas as pd
import re
from st_aggrid import AgGrid, GridOptionsBuilder
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

def prepare_dataframe(df):
    def extraer_origen_destino(rutas):
        origens, destinos = [], []
        for ruta in rutas.splitlines():
            matches = re.findall(r"\((.*?)\)", ruta)
            if len(matches) > 0:
                origens.append(matches[0])
            if len(matches) > 1:
                destinos.append(matches[1])
        return {"origen": origens, "destino": destinos}

    def combine_transport_modality(row):
        if row['TRANSPORT_TYPE'] == "Maritime":
            return f"{row['TRANSPORT_TYPE']} - {row['MODALITY']}"
        else:
            return row['TRANSPORT_TYPE']

    if not df.empty and "ROUTES_INFO" in df.columns:
        df[["origen", "destino"]] = df["ROUTES_INFO"].apply(
            lambda x: pd.Series(extraer_origen_destino(x))
        )
        df['TRANSPORT_COMBO'] = df.apply(combine_transport_modality, axis=1)
    return df


def create_filters(df_full, key_prefix):
    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    with col1:
        origen_options = sorted(set(o for sublist in df_full["origen"].dropna() for o in sublist))
        selected_origen = st.multiselect('**Port of Origin**', origen_options, key=f"{key_prefix}_origen")

    with col2:
        destino_options = sorted(set(d for sublist in df_full["destino"].dropna() for d in sublist))
        selected_destino = st.multiselect('**Port of Destination**', destino_options, key=f"{key_prefix}_destino")

    with col3:
        all_services = set()
        for service in df_full['SERVICE'].dropna():
            splitted = re.split(r'[,\n;]+', service)
            splitted = [item.strip() for item in splitted if item.strip()]
            all_services.update(splitted)
        service_options = sorted(all_services)
        selected_service = st.multiselect('**Service Requested**', service_options, key=f"{key_prefix}_service")

    with col4:
        transport_options = sorted(df_full['TRANSPORT_COMBO'].dropna().unique())
        selected_transport = st.multiselect("**Transport/Modality**", transport_options, key=f"{key_prefix}_transport")

    with col5:
        all_containers = set()
        for container_str in df_full['TYPE_CONTAINER'].dropna():
            splitted = re.split(r'[,\n;]+', container_str)
            splitted = [item.strip() for item in splitted if item.strip()]
            all_containers.update(splitted)
        container_options = sorted(all_containers)
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
    if not df_filtered.empty:
        gb = GridOptionsBuilder.from_dataframe(df_filtered)
        visible_columns = ["REQUEST_ID", "CLIENT", "ROUTES_INFO", "INCOTERM", 
                        "COMMODITY", "TRANSPORT_TYPE", "MODALITY", 
                        "TYPE_CONTAINER", "STATUS", "DESTINATION", "CUSTOMER"]

        for col in df_filtered.columns:
            if col not in visible_columns:
                gb.configure_column(col, hide=True)
            else:
                gb.configure_column(col)

        gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)  
        gb.configure_selection("single", use_checkbox=True)  
        gb.configure_grid_options(domLayout='autoHeight')

        grid_options = gb.build()
        grid_key = f"aggrid_{source}"

        grid_response = AgGrid(df_filtered, gridOptions=grid_options,  key=grid_key,
                        enable_enterprise_modules=True, 
                        fit_columns_on_grid_load=True, height=600)

        selected_rows = grid_response.get("selected_rows")

        if selected_rows is not None and len(selected_rows) > 0:
            handle_row_selection(selected_rows, source)

def handle_row_selection(selected_rows, source):
    if selected_rows is not None and len(selected_rows) > 0:
        selected_df = pd.DataFrame(selected_rows)
        exclude_columns = ["origen", "destino", "EMAIL_SENT", "FEEDBACK", "ASSIGNED_TO", "DEADLINE", "TRANSPORT_COMBO"]
        selected_df = selected_df.drop(columns=[col for col in exclude_columns if col in selected_df.columns])

        selected_df = selected_df.T.reset_index()
        selected_df.columns = ["Field", "Value"]
        selected_df["Value"] = selected_df["Value"].astype(str)
        selected_df = selected_df[selected_df["Value"].str.strip() != ""]
        selected_df = selected_df[selected_df["Value"].str.lower() != "nan"]
        selected_df = selected_df.dropna()
        selected_df.set_index("Field", inplace=True)

        st.session_state.selected_requested_quotation = None
        st.session_state.selected_ground_quotation = None
        st.session_state.selected_contract = None

        if source == "requested":
            st.session_state.selected_requested_quotation = selected_df
            st.session_state.selected_ground_quotation = None
            st.session_state.selected_contract = None
        elif source == "ground":
            st.session_state.selected_ground_quotation = selected_df
            st.session_state.selected_requested_quotation = None
            st.session_state.selected_contract = None
        elif source == "contract":
            st.session_state.selected_contract = selected_df
            st.session_state.selected_requested_quotation = None
            st.session_state.selected_ground_quotation = None

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

def save_feedback_to_sheets(feedback_data):
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["google_sheets_credentials"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)

        spreadsheet_id = st.secrets["general"]["time_sheet_id"]
        worksheet_name = "Quotations Feedback"


        sheet = client.open_by_key(spreadsheet_id)

        try:
            worksheet = sheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=worksheet_name, rows="1000", cols="10")
            headers = ["TIME","REQUEST ID", "COMMERCIAL", "QUOTATION TYPE", "ASSIGNATON STATUS", "REASON", "OTHER REASON", "COST", "TARGET"]
            worksheet.append_row(headers)
        
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
    if "reason_status" in st.session_state:
        st.session_state.reason_status = ""
    if "cost" in st.session_state:
        st.session_state.cost = 0.0
    if "target" in st.session_state:
        st.session_state.target = 0.0

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
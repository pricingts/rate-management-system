import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import os
import re
from st_aggrid import AgGrid, GridOptionsBuilder
from src.services.quotations_utils import *

def clean_text(value):
    if isinstance(value, str):
        value = value.replace("\n", " ") 
        value = " ".join(value.split()) 
    return value

@st.dialog("Quotation Details", width="large")
def show_dialog():
    dialog_type = st.session_state.get("dialog_type")

    if dialog_type == "requested":
        df = st.session_state.selected_requested_quotation
    elif dialog_type == "ground":
        df = st.session_state.selected_ground_quotation
    elif dialog_type == "contract":
        df = st.session_state.selected_contract
    else:
        df = None

    if isinstance(df, dict):
        df = pd.DataFrame(df)

    if isinstance(df, pd.DataFrame) and not df.empty:
        st.dataframe(df)
        request_id = df.loc['REQUEST_ID', 'Value']
        commercial = df.loc['COMMERCIAL', 'Value']
        type = dialog_type

        assigned = st.radio(
            "¿This Quotation has been Assigned?",
            ("Yes", "No"),
            key="assigned_status", horizontal=True, index=None
        )

        reason, other_reason = None, None
        cost, target = None, None

        if assigned == "Yes":
            if "REQUEST_ID" in df.index:
                st.markdown(f"### Great! Remember, your request ID is **{request_id}**")
            else:
                st.markdown("### Request ID not found.")

        elif assigned == "No":
            reason = st.selectbox(
                "What is the reason?", 
                [
                    "",
                    "Delay in rate delivery", 
                    "Uncompetitive prices", 
                    "Client chose another provider", 
                    "No response from the client", 
                    "Issues with transit times or availability", 
                    "Other"
                ],
                key="reason"
            )
            other_reason = ""
            cost, target = None, None

            if reason == "Uncompetitive prices":
                col1, col2 = st.columns(2)
                with col1:
                    cost = st.number_input("Enter Cost", key="cost")
                with col2:
                    target = st.number_input("Enter Target", key="target")
            elif reason == "Other":
                other_reason = st.text_input("Write the reason", key="other_reason")
        
        if assigned in ("Yes", "No"):
            feedback_data = {
                    "request_id": request_id,
                    "commercial": commercial,
                    "type": type,
                    "assigned_status":assigned,
                    "reason": reason,
                    "other_reason": other_reason,
                    "cost": cost,
                    "target": target
                }

            if st.button("Send Information"):
                with st.spinner("Sending information..."):
                    success, message = save_feedback_to_sheets(feedback_data)
                    if success:
                        st.success(message)
                        st.session_state.open_dialog = False
                        st.session_state.dialog_type = None
                        st.session_state.selected_requested_quotation = None
                        st.session_state.selected_ground_quotation = None
                        st.session_state.selected_contract = None
                        reset_dialog_inputs()
                    else:
                        st.error(message)

def show(role):
    if "open_dialog" not in st.session_state:
        st.session_state.open_dialog = False
    if "selected_requested_quotation" not in st.session_state:
        st.session_state.selected_requested_quotation = None
    if "selected_ground_quotation" not in st.session_state:
        st.session_state.selected_ground_quotation = None
    if "selected_contract" not in st.session_state:
        st.session_state.selected_contract = None
    if "dialog_type" not in st.session_state:
        st.session_state.dialog_type = None

    quotations_requested = st.secrets["general"]["quotations_requested"]
    quotations_contracts = st.secrets["general"]["costs_sales_contracts"]

    creds = Credentials.from_service_account_info(
        st.secrets["google_sheets_credentials"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

    client = gspread.authorize(creds)

    @st.cache_data(ttl=1800)
    def load_data_from_sheets(sheet_id: str, worksheet_name: str) -> pd.DataFrame:
        try:
            sheet = client.open_by_key(sheet_id)
            worksheet = sheet.worksheet(worksheet_name)
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)

            return df
        except Exception as e:
            st.error(f"Error al cargar datos desde Google Sheets ({worksheet_name}): {str(e)}")
            return pd.DataFrame()

    name = st.experimental_user.name
    email = st.experimental_user.email

    if role == "commercial":
        request_df = load_data_from_sheets(quotations_requested, "All Quotes")
        contracts_df = load_data_from_sheets(quotations_contracts, "CONTRATOS")
        request_df = request_df[request_df["COMMERCIAL"] == name]
        contracts_df = contracts_df[contracts_df["Commercial"] == name]
    elif role == "pricing":
        request_df = load_data_from_sheets(quotations_requested, "All Quotes")
        contracts_df = load_data_from_sheets(quotations_contracts, "CONTRATOS")
        name_map = {
            'customer9@tradingsol.com': 'Luis',
            'pricing11@tradingsol.com': 'Esthefy',
            'pricing6@tradingsol.com': 'Heidi',
            'pricing8@tradingsol.com': 'Mafe'
        }
        if email in name_map:
            name = name_map[email]
            request_df = request_df[request_df["ASSIGNED_TO"].apply(lambda x: name in [correo.strip() for correo in str(x).split(",")])]
    elif role == "ground":
        request_df = load_data_from_sheets(quotations_requested, "Ground Quotations")
        contracts_df = pd.DataFrame()
    elif role == "admin":
        request_df = load_data_from_sheets(quotations_requested, "All Quotes")
        ground_df = load_data_from_sheets(quotations_requested, "Ground Quotations") #incluir cotizaciones de graound
        contracts_df = load_data_from_sheets(quotations_contracts, "CONTRATOS")
    else:
        request_df = pd.DataFrame()
        contracts_df = pd.DataFrame()

    tabs_names = ["Quotations Requested", "Contracts Quotations"]

    if role in ["ground", "admin"]:
        tabs_names.append("Ground Quotations")

    tab_objs = st.tabs(tabs_names)

    with tab_objs[0]:

        key_prefix = "requested"

        col1, col2, col3 = st.columns([1,  0.18, 0.18])
        with col1:
            st.header("Quotations Requested")
        with col2:
            st.write(" ")
            st.button("Clear Filters", on_click= lambda:clear_filters(key_prefix), key=f"clear_requested")
        with col3:
            st.write(" ")
            if st.button("Refresh Data", key="button_2"):
                load_data_from_sheets.clear() 
                st.rerun()

        df_full = request_df.copy()

        if df_full is None or df_full.empty:
            st.error("No data available. Try to update")
            df_filtered = pd.DataFrame()
        else:
            df_full = prepare_dataframe(df_full)
            df_filtered = df_full.copy()

            initialize_filters(key_prefix)

            selected_origen, selected_destino, selected_service, selected_transport, selected_container, selected_client = create_filters(df_full, key_prefix)
            df_filtered = apply_filters(df_full, selected_origen, selected_destino, selected_client, selected_service, selected_container, selected_transport)
            show_metrics(df_filtered)
            show_grid(df_filtered, "requested")

    # -------------------- CONTRACTS QUOTATIONS --------------------
    with tab_objs[1]:

        key_prefix = "contracts"

        col1, col2, col3 = st.columns([1,  0.18, 0.18])
        with col1:
            st.header("Contracts Quotations")
        with col2:
            st.write(" ")
            st.button("Clear Filters", on_click= lambda:clear_filters(key_prefix), key=f"clear_contracts")
        with col3:
            st.write(" ")
            if st.button("Refresh Data", key="button_3"):
                load_data_from_sheets.clear() 
                st.rerun()

        df_full = contracts_df.copy()
        if df_full is None or df_full.empty:
            st.error("No data available. Try to update")
            df_filtered = pd.DataFrame()

        else:
            initialize_filters(key_prefix)

            col1, col2 = st.columns(2)
            col3, col4 = st.columns(2)
            with col1:
                pol_op = sorted(df_full['POL'].dropna().unique())
                selected_origin = st.multiselect("**Port of Origin**", pol_op, key=f"{key_prefix}_pol")
            with col2:
                pod_op = sorted(df_full['POD'].dropna().unique())
                selected_destination = st.multiselect("**Port of Destination**", pod_op, key=f"{key_prefix}_pod")
            with col3:
                cargo_op = sorted(df_full['Cargo Types'].dropna().unique())
                selected_cargo = st.multiselect("**Container Type**", cargo_op, key=f"{key_prefix}_cargo")
            with col4:
                cliente_op = sorted(df_full['Cliente'].dropna().astype(str).unique())
                selected_client = st.multiselect("**Client**", cliente_op, key=f"{key_prefix}_client")

            df_filtered = filter_contracts(df_full, selected_origin, selected_destination, selected_cargo, selected_client)

            df_filtered['Total Cost'] = df_filtered['Total Cost'].str.replace('$', '', regex=False).astype(float)
            df_filtered['Total Sale'] = df_filtered['Total Sale'].str.replace('$', '', regex=False).astype(float)
            df_filtered['Total Profit'] = df_filtered['Total Profit'].str.replace('$', '', regex=False).astype(float)

            quotations_quantity = df_filtered.shape[0]
            total_cost = df_filtered['Total Cost'].sum()
            total_sale = df_filtered['Total Sale'].sum()
            total_profit = df_filtered['Total Profit'].sum()
            col1, col2, col3, col4 = st.columns(4)

            col1.metric(label="Number of Quotations Downloaded", value=quotations_quantity)
            col2.metric(label="Total Cost", value=f"${total_cost}")
            col3.metric(label="Total Sale", value=f"${total_sale}")
            col4.metric(label="Total Profit", value=f"${total_profit}")

            if not df_filtered.empty:
                for col in df_filtered.select_dtypes(include=["object"]).columns:
                    df_filtered[col] = df_filtered[col].apply(clean_text)

                gb = GridOptionsBuilder.from_dataframe(df_filtered)
                gb.configure_pagination(paginationAutoPageSize=True, paginationPageSize=20) 
                gb.configure_selection("single", use_checkbox=True)  
                gb.configure_grid_options(domLayout='autoHeight')

                grid_options = gb.build()

                grid_response = AgGrid(df_filtered, gridOptions=grid_options, 
                                enable_enterprise_modules=True, 
                                fit_columns_on_grid_load=True, height=600)

                selected_rows = grid_response.get("selected_rows")

                if selected_rows is not None and len(selected_rows) > 0:
                    handle_row_selection(selected_rows, "contract")

    if role in ["ground", "admin"]:
        with tab_objs[2]:
            key_prefix = "ground"
            col1, col2, col3 = st.columns([1,  0.18, 0.18])
            with col1:
                st.header("Ground Quotations")
            with col2:
                st.write(" ")
                st.button("Clear Filters", on_click= lambda:clear_filters(key_prefix), key=f"clear_ground")
            with col3:
                st.write(" ")
                if st.button("Refresh Data", key="button_4"):
                    load_data_from_sheets.clear() 
                    st.rerun()

            df_full = ground_df.copy()

            if df_full is None or df_full.empty:
                st.error("No data available. Try to update")
                df_filtered = pd.DataFrame()
            else:
                df_full = ground_df.copy()

            if df_full is None or df_full.empty:
                st.error("No data available. Try to update")
                df_filtered = pd.DataFrame()
            else:
                df_full = prepare_dataframe(df_full)
                df_filtered = df_full.copy()

                initialize_filters(key_prefix)

                selected_origen, selected_destino, selected_service, selected_transport, selected_container, selected_client = create_filters(df_full, key_prefix)
                df_filtered = apply_filters(df_full, selected_origen, selected_destino, selected_client, selected_service, selected_container, selected_transport)
                show_metrics(df_filtered)
                show_grid(df_filtered, "ground")

    if st.session_state.get("open_dialog", False):
        show_dialog()



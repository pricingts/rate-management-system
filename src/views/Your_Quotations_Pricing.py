import streamlit as st
import pandas as pd
from src.services.quotations_utils import *
from ..common.role_utils import get_role_dfs
from src.common.google_sheets import load_all_records
from src.common.transformers import clean_commercial_names, clean_request_id, convert_time_columns, ensure_all_columns_are_strings, merge_requested_and_ground

def clean_text(value):
    if isinstance(value, str):
        value = value.replace("\n", " ") 
        value = " ".join(value.split()) 
    return value

@st.dialog("Quotation Details", width="large")
def show_dialog():
    st.session_state.open_dialog = False

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

    name = st.experimental_user.name
    email = st.experimental_user.email

    request_df, contracts_df, ground_df = get_role_dfs(role, name, email)

    request_df = convert_time_columns(request_df, dayfirst=True)
    contracts_df = convert_time_columns(contracts_df)
    ground_df = convert_time_columns(ground_df)

    request_df = ensure_all_columns_are_strings(request_df)
    contracts_df = ensure_all_columns_are_strings(contracts_df)
    ground_df = ensure_all_columns_are_strings(ground_df)

    request_df = clean_request_id(request_df)
    contracts_df = clean_request_id(contracts_df)
    ground_df = clean_request_id(ground_df)

    request_df = clean_commercial_names(request_df)

    tabs_names = ["Quotations Requested", "Contracts Quotations"]

    if role in ["ground", "admin", "pricing"]:
        tabs_names.append("Ground Quotations")

    if "last_active_tab" not in st.session_state:
        st.session_state.last_active_tab = tabs_names[0]

    tab_objs = st.tabs(tabs_names)

    with tab_objs[0]:

        key_prefix = "requested"

        col1, col2, col3 = st.columns([1,  0.18, 0.18])
        with col1:
            st.header("Quotations Requested")
        with col2:
            st.write(" ")
            if st.button("Clear Filters", key="clear_requested"):
                clear_filters(key_prefix)
                st.rerun()

        with col3:
            st.write(" ")
            if st.button("Refresh Data", key="button_2"):
                load_all_records.clear() 
                st.rerun()

        df_full = request_df.copy()

        if df_full is None or df_full.empty:
            st.error("No data available. Try to update")
            df_filtered = pd.DataFrame()
        else:
            df_full = prepare_dataframe(df_full)
            texto_cols = ["commodity"]
            for col in texto_cols:
                if col in df_full:
                    df_full[col] = df_full[col].astype(str)

            df_full['time'] = pd.to_datetime(df_full['time'], format='%d/%m/%Y %H:%M:%S')
            df_full = df_full.sort_values(by='time', ascending=False)

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
            if st.button("Clear Filters", key="clear_contracts"):
                clear_filters(key_prefix)
                st.rerun()
        with col3:
            st.write(" ")
            if st.button("Refresh Data", key="button_3"):
                load_all_records.clear() 
                st.rerun()

        df_full = contracts_df.copy()
        if df_full is None or df_full.empty:
            st.error("No data available. Try to update")
            df_filtered = pd.DataFrame()

        else:
            df_full['time'] = pd.to_datetime(df_full['time'], format='%Y-%m-%d %H:%M:%S')
            df_full = df_full.sort_values(by='time', ascending=False)

            initialize_filters(key_prefix)

            col1, col2 = st.columns(2)
            col3, col4 = st.columns(2)
            with col1:
                pol_op = sorted(df_full['pol'].dropna().unique())
                selected_origin = st.multiselect("**Port of Origin**", pol_op, key=f"{key_prefix}_pol")
            with col2:
                pod_op = sorted(df_full['pod'].dropna().unique())
                selected_destination = st.multiselect("**Port of Destination**", pod_op, key=f"{key_prefix}_pod")
            with col3:
                cargo_op = sorted(df_full['cargo types'].dropna().unique())
                selected_cargo = st.multiselect("**Container Type**", cargo_op, key=f"{key_prefix}_cargo")
            with col4:
                cliente_op = sorted(df_full['cliente'].dropna().astype(str).unique())
                selected_client = st.multiselect("**Client**", cliente_op, key=f"{key_prefix}_client")

            df_filtered = filter_contracts(df_full, selected_origin, selected_destination, selected_cargo, selected_client)

            df_filtered['total cost'] = df_filtered['total cost'].str.replace('$', '', regex=False).astype(float)
            df_filtered['total sale'] = df_filtered['total sale'].str.replace('$', '', regex=False).astype(float)
            df_filtered['total profit'] = df_filtered['total profit'].str.replace('$', '', regex=False).astype(float)

            quotations_quantity = df_filtered.shape[0]
            total_cost = df_filtered['total cost'].sum()
            total_sale = df_filtered['total sale'].sum()
            total_profit = df_filtered['total profit'].sum()
            col1, col2, col3, col4 = st.columns(4)

            col1.metric(label="**Quotations Downloaded**", value=quotations_quantity)
            col2.metric(label="**Total Cost**", value=f"${total_cost}")
            col3.metric(label="**Total Sale**", value=f"${total_sale}")
            col4.metric(label="**Total Profit**", value=f"${total_profit}")

            if not df_filtered.empty:
                for col in df_filtered.select_dtypes(include=["object"]).columns:
                    df_filtered[col] = df_filtered[col].apply(clean_text)

                request_ids = df_filtered["request_id"].tolist()
                request_ids.insert(0, "-- Select a request --")

                selected_id = st.selectbox("Select a request to view details", request_ids)
                for col in df_filtered.select_dtypes(include=["object"]).columns:
                    df_filtered[col] = df_filtered[col].astype(str)

                st.dataframe(df_filtered, use_container_width=True, height=600, hide_index=True)

                selected_row = df_filtered[df_filtered["request_id"] == selected_id]
                if not selected_row.empty:
                    handle_row_selection(selected_row.to_dict("records"), "contract")

    if role in ["ground", "admin"]:
        with tab_objs[2]:

            key_prefix = "ground"
            col1, col2, col3 = st.columns([1,  0.18, 0.18])
            with col1:
                st.header("Ground Quotations")
            with col2:
                st.write(" ")
                if st.button("Clear Filters", key="clear_ground"):
                    clear_filters(key_prefix)
                    st.rerun()
            with col3:
                st.write(" ")
                if st.button("Refresh Data", key="button_4"):
                    load_all_records.clear() 
                    st.rerun()

            df_full = ground_df.copy()
            st.write(df_full)

            df_full = df_full[df_full['service'].str.contains("Ground Transportation", case=False, na=False)]

            if df_full is None or df_full.empty:
                st.error("No data available. Try to update")
                df_filtered = pd.DataFrame()
            else:
                df_full = prepare_dataframe(df_full)

                df_full['time'] = pd.to_datetime(df_full['time'], format='%Y-%m-%d %H:%M:%S')
                df_full = df_full.sort_values(by='time', ascending=False)

                initialize_filters(key_prefix)

                selected_origen, selected_destino, selected_service, selected_transport, selected_container, selected_client = create_filters(df_full, key_prefix)
                df_filtered = apply_filters(df_full, selected_origen, selected_destino, selected_client, selected_service, selected_container, selected_transport)
                show_metrics(df_filtered)
                show_grid(df_filtered, key_prefix)

    if st.session_state.get("open_dialog", False):
        show_dialog()
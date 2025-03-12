import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import os
import re
import plotly.express as px
from utils import get_name
from st_aggrid import AgGrid, GridOptionsBuilder

def clean_text(value):
    if isinstance(value, str):
        value = value.replace("\n", " ") 
        value = " ".join(value.split()) 
    return value

def show(user):
    name = get_name(user)

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

    request_df = load_data_from_sheets(quotations_requested, "All Quotes")
    contracts_df = load_data_from_sheets(quotations_contracts, "CONTRATOS")

    #st.write(request_df)
    #st.write(contracts_df)

    #if name:
    #    df_filtered = df[df["COMMERCIAL"] == name]

    tabs = st.tabs(["All Quotations", "Quotations Requested", "Contracts Quotations"])

    if "selected_quotation" not in st.session_state:
        st.session_state.selected_quotation = None

    if "selected_contract" not in st.session_state:
        st.session_state.selected_contract = None

    with tabs[0]:
        st.header("All Quotations")

    with tabs[1]:
        st.header("Quotations Requested")
        df_full = request_df.copy()

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

        df_full[["origen", "destino"]] = df_full["ROUTES_INFO"].apply(
            lambda x: pd.Series(extraer_origen_destino(x))
        )

        df_full['TRANSPORT_COMBO'] = df_full.apply(combine_transport_modality, axis=1)

        df_filtered = df_full.copy()
        col1, col2, col3 = st.columns(3)
        col4, col5, col6 = st.columns(3)

        with col1:
            origen_options = sorted(set(o for sublist in df_full["origen"].dropna() for o in sublist))
            selected_origen = st.multiselect('**Port of Origin**', origen_options, key="origen")

        with col2:
            destino_options = sorted(set(d for sublist in df_full["destino"].dropna() for d in sublist))
            selected_destino = st.multiselect('**Port of Destination**', destino_options, key="destino")

        with col3:
            all_services = set()
            for service in df_full['SERVICE'].dropna():
                splitted = re.split(r'[,\n;]+', service)
                splitted = [item.strip() for item in splitted if item.strip() != ""]
                all_services.update(splitted)
            service_options = sorted(all_services)
            selected_service = st.multiselect('**Service Requested**', service_options, key="service")

        with col4:
            transport_options = sorted(df_full['TRANSPORT_COMBO'].dropna().unique())
            selected_transport = st.multiselect("**Transport/Modality**", transport_options)

        with col5: 
            all_containers = set()
            for container_str in df_full['TYPE_CONTAINER'].dropna():
                splitted = re.split(r'[,\n;]+', container_str)
                splitted = [item.strip() for item in splitted if item.strip() != ""]
                all_containers.update(splitted)
            container_options = sorted(all_containers)
            selected_container = st.multiselect('**Container Type**', container_options, key="cont_type")

        with col6:
            client_options = sorted(df_full['CLIENT'].dropna().unique())
            selected_client = st.multiselect('**Client**', client_options, key="client")


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

        request_quantity = df_filtered.shape[0]
        counts = df_filtered["TRANSPORT_COMBO"].value_counts()
        maritime_fcl_count = counts.get("Maritime - FCL", 0)
        maritime_lcl_count = counts.get("Maritime - LCL", 0)
        air_count = counts.get("Air", 0)

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(label="Number of Quotations Requested", value=request_quantity)
        col2.metric(label="Maritime - FCL", value=maritime_fcl_count)
        col3.metric(label="Maritime - LCL", value=maritime_lcl_count)
        col4.metric(label="Air", value=air_count)


        # -------------------- DATAFRAME --------------------
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

            grid_response = AgGrid(df_filtered, gridOptions=grid_options, 
                        enable_enterprise_modules=True, 
                        fit_columns_on_grid_load=True, height=600)

            selected_rows = grid_response.get("selected_rows")

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

                st.session_state.selected_quotation = selected_df
        else:
            st.warning("No data available to display.")

        if st.session_state.selected_quotation is not None:
            @st.dialog("Quotation Details", width="large")
            def show_selected_quotation():
                st.table(st.session_state.selected_quotation)

            show_selected_quotation()

    # -------------------- CONTRACTS QUOTATIONS --------------------
    with tabs[2]:
        st.header("Contracts Quotations")

        df_full = contracts_df.copy()
        df_full["Time"] = pd.to_datetime(df_full["Time"], errors="coerce")

        col1, col2, col3 = st.columns(3)
        col4, col5 = st.columns(2)
        with col1:
            unique_dates = sorted(df_full["Time"].dropna().dt.date.unique())
            selected_date = st.date_input("**Date**", value=unique_dates[0] if unique_dates else None)
        with col2:
            pol_op = sorted(df_full['POL'].dropna().unique())
            selected_origin = st.multiselect("**Port of Origin**", pol_op)
        with col3:
            pod_op = sorted(df_full['POD'].dropna().unique())
            selected_destination = st.multiselect("**Port of Destination**", pod_op)
        with col4:
            cargo_op = sorted(df_full['Cargo Types'].dropna().unique())
            selected_cargo = st.multiselect("**Container Type**", cargo_op)
        with col5:
            cliente_op = sorted(df_full['Cliente'].dropna().unique())
            selected_client = st.multiselect("**Client**", cliente_op)

        df_filtered = df_full.copy()
        if selected_date:
            df_filtered = df_filtered[df_filtered["Time"].dt.date == selected_date]
        if selected_origin:
            df_filtered = df_filtered[df_filtered["POL"].apply(lambda x: any(o in x for o in selected_origin))]
        if selected_destination:
            df_filtered = df_filtered[df_filtered["POD"].apply(lambda x: any(o in x for o in selected_destination))]
        if selected_cargo:
            df_filtered = df_filtered[df_filtered["Cargo Types"].apply(lambda x: any(o in x for o in selected_cargo))]
        if selected_client:
            df_filtered = df_filtered[df_filtered["Cliente"].apply(lambda x: any(o in x for o in selected_client))]
        
        quotations_quantity = df_filtered.shape[0]
        total_sale = df_filtered['Total Sale'].sum()
        total_profit = df_filtered['Total Profit'].sum()
        col1, col2, col3 = st.columns(3)

        col1.metric(label="Number of Quotations Downloaded", value=quotations_quantity)
        col2.metric(label="Total Sale", value=total_sale)
        col3.metric(label="Total Profit", value=total_profit)

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
                selected_df = pd.DataFrame(selected_rows)

                selected_df = selected_df.T.reset_index()
                selected_df.columns = ["Field", "Value"] 
                selected_df["Value"] = selected_df["Value"].astype(str)

                selected_df = selected_df[selected_df["Value"].str.strip() != ""] 
                selected_df = selected_df[selected_df["Value"].str.lower() != "nan"]  
                selected_df = selected_df.dropna()

                selected_df.set_index("Field", inplace=True)  
                st.session_state.selected_contract = selected_df
        else:
            st.warning("No data available to display.")

        if st.session_state.selected_contract is not None:
            @st.dialog("Contract Details", width="large")
            def show_selected_contract():
                st.table(st.session_state.selected_contract)

            show_selected_contract()

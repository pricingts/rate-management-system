import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
import numpy as np
from cotizacion import *
import json
from utils import load_existing_ids_from_sheets, log_time
import pytz
from datetime import datetime
import datetime as dt
from utils import get_name

colombia_timezone = pytz.timezone('America/Bogota')

def get_valid_value(primary, fallback):
    if pd.notna(primary) and str(primary).strip(): 
        return primary
    elif pd.notna(fallback) and str(fallback).strip():
        return fallback
    else:
        return "" 


def parse_price(value):
    if isinstance(value, str) and value.strip().upper() == "INCLUIDO":
        return "INCLUIDO"
    try:
        return float(value.replace('$', '').replace('.', '').replace(',', '.'))
    except ValueError:
        return value 

def validate_inputs(client, cargo_types, incoterm, cargo_value, selected_surcharges, surcharge_values):
    errors = []

    if not client.strip():
        errors.append("⚠️ Please enter a client name.")

    if not cargo_types:
        errors.append("⚠️ Please select at least one container.")

    if incoterm == "CIF" and cargo_value == 0:
        errors.append("⚠️ Cargo value must be greater than 0.")

    if not selected_surcharges:
        errors.append("⚠️ Please select at least one surcharge.")

    has_invalid_sales = any(sale == 0 for surcharge in surcharge_values for sale in surcharge_values[surcharge].values())
    if has_invalid_sales:
        errors.append("❌ Sales values must be greater than 0.")

    return errors

def generate_request_id():
    if "generated_ids" not in st.session_state:
        st.session_state["generated_ids"] = set()

    existing_ids = load_existing_ids_from_sheets()
    new_sequence_ids = [
        int(id[1:]) for id in existing_ids 
        if id.startswith('Q') and id[1:].isdigit()
    ]

    if new_sequence_ids:
        next_id = max(new_sequence_ids) + 1
    else:
        next_id = 1 

    unique_id = f"Q{next_id:04d}"

    st.session_state["generated_ids"].add(unique_id)
    return unique_id


def save_to_google_sheets(data, start_time):
    SPREADSHEET_ID = st.secrets['general']['costs_sales_contracts']
    SHEET_NAME = "CONTRATOS"

    credentials = Credentials.from_service_account_info(
        st.secrets["google_sheets_credentials"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", 
                "https://www.googleapis.com/auth/drive"]
    )

    gc = gspread.authorize(credentials)
    try:
        sheet = gc.open_by_key(SPREADSHEET_ID)
        try:
            worksheet = sheet.worksheet(SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=SHEET_NAME, rows="1000", cols="30")
            st.warning(f"Worksheet '{SHEET_NAME}' was created.")
            headers = [
                "Cotización ID", "Commercial", "Time", "Cliente", "Incoterm", "POL", "POD", "Commodity", "Contrato ID",
                "Cargo Types", "Cargo Value", "Surcharges (Costos)", "Surcharges (Ventas)", 
                "Additional Surcharges (Costos)", "Additional Surcharges (Ventas)", 
                "Total Cost", "Total Sale", "Total Profit"
            ]

            worksheet.append_row(headers)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("The specified Google Sheets document was not found.")
        return

    if not st.session_state.get("request_id"): 
        st.session_state["request_id"] = generate_request_id()

    client = data["client"]
    incoterm = data["incoterm"]
    cargo_types = "\n".join(data["cargo_types"]) 
    cargo_value = data["cargo_value"]
    total_profit = data["total_profit"]
    commercial = data["commercial"]

    total_cost = 0
    total_sale = 0

    surcharge_costs = []
    surcharge_sales = []
    for surcharge, details in data["surcharges"].items():
        for cont_type, values in details.items():
            cost = values['cost']
            sale = values['sale']
            surcharge_costs.append(f"{surcharge} {cont_type}: ${cost:.2f}")
            surcharge_sales.append(f"{surcharge} {cont_type}: ${sale:.2f}")
            total_cost += cost
            total_sale += sale

    surcharge_costs_str = "\n".join(surcharge_costs) 
    surcharge_sales_str = "\n".join(surcharge_sales)

    additional_surcharge_costs = []
    additional_surcharge_sales = []
    for add_surcharge in data["additional_surcharges"]:
        cost = add_surcharge['cost']
        sale = add_surcharge['sale']
        additional_surcharge_costs.append(f"{add_surcharge['concept']}: ${cost:.2f}")
        additional_surcharge_sales.append(f"{add_surcharge['concept']}: ${sale:.2f}")
        total_cost += cost
        total_sale += sale

    additional_surcharge_costs_str = "\n".join(additional_surcharge_costs) 
    additional_surcharge_sales_str = "\n".join(additional_surcharge_sales)

    st.session_state["end_time"] = datetime.now(pytz.utc).astimezone(colombia_timezone)
    end_time = st.session_state.get("end_time", None)
    if end_time is not None:
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
    else:
        st.error("Error: 'end_time' no fue asignado correctamente.")
        return

    start_time = st.session_state.get("start_time", None)
    if start_time and end_time:
        duration = (end_time - start_time).total_seconds()
    else:
        st.error("Error: 'start_time' o 'end_time' no están definidos. No se puede calcular la duración.")
        return

    row = [
        st.session_state["request_id"], commercial, end_time_str, client, incoterm, 
        data["pol"], data["pod"], data["commodity"], data["contract_id"],
        cargo_types, cargo_value, surcharge_costs_str, surcharge_sales_str, 
        additional_surcharge_costs_str, additional_surcharge_sales_str,
        f"${total_cost:.2f}", f"${total_sale:.2f}", f"${total_profit:.2f}"
    ]
    worksheet.append_row(row)
    
    log_time(start_time, end_time, duration, st.session_state["request_id"], quotation_type="Contracts")

incoterm_op = ['CIF', 'CFR', 'FOB', 'CPT', 'DAP']

@st.dialog("Generate Quotation", width="large")
def select_options(contrato_id, available_cargo_types, tabla_pivot):
    if st.session_state.get("start_time") is None:
        st.session_state["start_time"] = datetime.now(colombia_timezone)

    start_time = st.session_state["start_time"]

    incoterm = st.selectbox('Select Incoterm', incoterm_op, key=f'incoterm_{contrato_id}')
    client = st.text_input('Client', key=f'client_{contrato_id}')
    cargo_types = st.multiselect('Select Cargo Type', available_cargo_types, key=f'cargo_{contrato_id}')

    cargo_value = 0.0
    insurance_cost = 0.0

    if incoterm == "CIF":
        cargo_value = st.number_input(f'Enter Cargo Value', min_value=0.0, step=0.01, key=f'cargo_value_{contrato_id}')
        insurance_cost = round(cargo_value * (0.13/100) * 1.04, 2)
        st.write(f'**Cost of Insurance ${insurance_cost}**')

    if not cargo_types:
        st.warning('Please select a container to continue')
        return

    available_surcharges = [s for s in tabla_pivot.index if s in ["Origen", "Flete", "Destino", "Hbl", "Switch"]]
    selected_surcharges = st.multiselect('Select Surcharges', available_surcharges, key=f'surcharges_{contrato_id}')
    tabla_pivot = tabla_pivot.map(parse_price)

    surcharge_values = {surcharge: {} for surcharge in selected_surcharges}
    total_profit = 0

    cols = st.columns(len(cargo_types) * 2)
    for idx, cont in enumerate(cargo_types):
        with cols[idx * 2]:
            st.write(f"### {cont}")

    for surcharge in selected_surcharges:
        cols = st.columns(len(cargo_types) * 2) 

        for idx, cont in enumerate(cargo_types):
            with cols[idx * 2]:
                if surcharge in tabla_pivot.index and cont in tabla_pivot.columns:
                    cost_value = tabla_pivot.at[surcharge, cont]
                    try:
                        if isinstance(cost_value, str) and cost_value.upper() == "INCLUIDO":
                            cost_display = "INCLUIDO"
                            cost_value = 0.0
                        else:
                            cost_value = float(cost_value)
                            cost_display = f"${cost_value:.2f}"
                    except (KeyError, ValueError):
                        cost_display = "Not Available"
                        cost_value = 0.0
                else:
                    cost_display = "Not Available"
                    cost_value = 0.0

                st.write(f'**Cost of {surcharge}**')
                st.write(cost_display)

            with cols[idx * 2 + 1]: 
                sale = st.number_input(f'Sale of {surcharge}', min_value=0.0, step=0.01, key=f'value_{surcharge}_{cont}_{contrato_id}')
                surcharge_values[surcharge][cont] = sale

            profit = sale - cost_value
            total_profit += profit

            surcharge_values[surcharge][cont] = {
                "cost": cost_value,
                "sale": sale
            }

    st.write("### Add Additional Surcharges")
    if "additional_surcharges" not in st.session_state:
        st.session_state["additional_surcharges"] = []

    if st.button("Add Surcharge"):
        st.session_state["additional_surcharges"].append({"concept": "", "cost": 0.0, "sale": 0.0})

    def remove_surcharge(index):
        if 0 <= index < len(st.session_state["additional_surcharges"]):
            del st.session_state["additional_surcharges"][index]

    to_remove = []
    for i, surcharge in enumerate(st.session_state["additional_surcharges"]):
        col1, col2, col3, col4 = st.columns([2.5, 1, 1, 0.5])
        with col1:
            surcharge["concept"] = st.text_input(f"Concept", surcharge["concept"], key=f'concept_{i}_{contrato_id}')
        with col2:
            surcharge["cost"] = st.number_input(f"Cost", min_value=0.0, step=0.01, key=f'cost_{i}_{contrato_id}')
        with col3:
            surcharge["sale"] = st.number_input(f"Sale", min_value=0.0, step=0.01, key=f'sale_{i}_{contrato_id}')
        with col4:
            st.write(" ")
            st.write(" ")
            st.button("❌", key=f'remove_{i}', on_click=remove_surcharge, args=(i,)) 

        total_profit += surcharge["sale"] - surcharge["cost"]
    
    for i in sorted(to_remove, reverse=True):
        del st.session_state["additional_surcharges"][i]
    
    st.write(f'**Total Profit: ${total_profit:.2f}**')

    if st.button("Generate Quotation"):
        errors = validate_inputs(client, cargo_types, incoterm, cargo_value, selected_surcharges, surcharge_values)

        if errors:
            for error in errors:
                st.error(error)
            return

        quotation_data = {
            "client": client,
            "incoterm": incoterm,
            "cargo_types": cargo_types,
            "cargo_value": cargo_value,
            "surcharges": surcharge_values,
            "additional_surcharges": st.session_state["additional_surcharges"],
            "total_profit": total_profit,
            "pol": st.session_state["selected_data"].get("POL", ""),
            "pod": st.session_state["selected_data"].get("POD", ""),
            "commodity": st.session_state["selected_data"].get("Details", {}).get("Commodities", ""),
            "commercial": st.session_state["selected_data"].get("Commercial", ""),
            "contract_id": contrato_id  
    }

        st.write(quotation_data)

        save_to_google_sheets(quotation_data, start_time)

        st.success("Quotation saved successfully to Google Sheets!")
        
        pdf_filename = generate_quotation(quotation_data)

        with open(pdf_filename, "rb") as f:
            pdf_bytes = f.read()

        st.download_button(
            label="Descargar Cotización",
            data=pdf_bytes,
            file_name="quotation.pdf",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def show(user):
    name = get_name(user)

    if name in ["Stephanie Bruges", "Catherine Silva"]:
        html_code = """
        <div style="display: flex; justify-content: center;">
            <iframe width="1000" height="700" 
                src="https://lookerstudio.google.com/embed/reporting/d6fe2354-5259-47c2-9a7c-49a27463cd1c/page/jvK2E" 
                frameborder="0" style="border:0;" allowfullscreen></iframe>
        </div>
        """
        st.markdown(html_code, unsafe_allow_html=True)

    else: 
        SPREADSHEET_ID = st.secrets["general"]["contratos_id"]
        SHEET_NAMES = ["CONTENEDORES", "TARIFAS SCRAP EXPO"]

        credentials = Credentials.from_service_account_info(
            st.secrets["contratos_credentials"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )

        @st.cache_data(ttl=10000)
        def load_data_from_gsheets(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
            gc = gspread.authorize(credentials)
            sh = gc.open_by_key(spreadsheet_id)
            worksheet = sh.worksheet(worksheet_name)
            data = worksheet.get_all_values()
            return pd.DataFrame(data[1:], columns=data[0]) if data else pd.DataFrame()

        @st.cache_data(ttl=1000000)
        def get_all_data(sheet_names: list):
            return {sheet: load_data_from_gsheets(SPREADSHEET_ID, sheet) for sheet in sheet_names}

        data_frames = get_all_data(SHEET_NAMES)
        contratos_df = data_frames["CONTENEDORES"]
        contratos_df = contratos_df[~contratos_df["Estado"].isin(["NO APROBADO", "EN PAUSA"])]

        tarifas_scrap = data_frames["TARIFAS SCRAP EXPO"]

        contratos_df["POL"] = contratos_df["POL"].astype(str)
        contratos_df["POD"] = contratos_df["POD"].astype(str)
        tarifas_scrap["POL"] = tarifas_scrap["POL"].astype(str)
        tarifas_scrap["POD"] = tarifas_scrap["POD"].astype(str)

        contratos_df['FECHA FIN FLETE'] = contratos_df['FECHA FIN FLETE'].str.strip() 
        contratos_df['FECHA FIN FLETE'] = pd.to_datetime(contratos_df['FECHA FIN FLETE'], format='%d/%m/%Y', errors='coerce')
        tarifas_scrap['FECHA FIN FLETE'] = pd.to_datetime(tarifas_scrap['FECHA FIN FLETE'], format='%d/%m/%Y', errors='coerce')

        common_columns = list(set(contratos_df.columns) & set(tarifas_scrap.columns))

        merged_df = pd.merge(contratos_df, tarifas_scrap, on=common_columns, how="outer")
        commodity = merged_df['COMMODITIES'].dropna().unique()

        st.header("Contracts Management")

        col1, col2 = st.columns(2)

        if "p_origen" not in st.session_state:
            st.session_state.p_origen = None
        if "p_destino" not in st.session_state:
            st.session_state.p_destino = None
        if "commodity" not in st.session_state:
            st.session_state.p_destino = None

        with col1:
            st.session_state.p_origen = st.selectbox("POL", merged_df["POL"].unique(), index=0)

        with col2:
            if st.session_state.p_origen:
                destinos_disponibles = merged_df[merged_df["POL"] == st.session_state.p_origen]["POD"].unique()
                st.session_state.p_destino = st.selectbox("POD", destinos_disponibles)

        if st.session_state.p_origen and st.session_state.p_destino:
            filtered_commodities = merged_df[
                (merged_df["POL"] == st.session_state.p_origen) & 
                (merged_df["POD"] == st.session_state.p_destino)
            ]["COMMODITIES"].dropna().unique()
            st.session_state.commodity_contracts = st.multiselect("Select Commodities", filtered_commodities)

        if st.session_state.p_origen and st.session_state.p_destino:
            p_origen = st.session_state.p_origen
            p_destino = st.session_state.p_destino
            commodity = st.session_state.commodity_contracts

            contratos = merged_df[(merged_df["POL"] == p_origen) & (merged_df["POD"] == p_destino) & (merged_df["COMMODITIES"].isin(commodity)) ]

            if not contratos.empty:
                hoy = dt.datetime.now()
                contratos_vigentes = contratos[pd.to_datetime(contratos["FECHA FIN FLETE"]) > hoy]

                if not contratos_vigentes.empty:
                    contratos_agrupados = contratos_vigentes.groupby(["Línea", "No CONTRATO"])
                    num_columns = 3

                    contrato_list = list(contratos_agrupados) 
                    num_contratos = len(contrato_list)

                    for row_start in range(0, num_contratos, num_columns):
                        row_contracts = contrato_list[row_start:row_start + num_columns]  
                        columnas = st.columns(num_columns)

                        for idx, ((linea, contrato_id), contrato_rows) in enumerate(row_contracts):
                            with columnas[idx]:
                                with st.expander(f"🚢 **{linea} - {contrato_id}**", expanded=True):
                                    contrato_info = contrato_rows.iloc[0]
                                    print(contrato_info.index)
                                    fields = {
                                        "Shipping Line": contrato_info.get("Línea", ""),
                                        "Commodities": contrato_info.get("COMMODITIES", ""),
                                        "HS Code": contrato_info.get("HS CODES", ""),
                                        "Shipper": contrato_info.get("SHIPPER", ""),
                                        "Free Days in Origin": get_valid_value(contrato_info.get("DÍAS ORIGEN", ""), contrato_info.get("FDO", "")),
                                        "Free Days in Destination": get_valid_value(contrato_info.get("DÍAS DESTINO APROBADOS", ""), contrato_info.get("FDD", "")),
                                        "Transit Time": contrato_info.get("TT", ""),
                                        "Route": contrato_info.get("RUTA", ""),
                                        "Suitable Food": contrato_info.get("APTO ALIMENTO", ""),
                                    }

                                    print(get_valid_value(contrato_info.get("DÍAS ORIGEN", ""), contrato_info.get("FDO", "")))
                                    print(get_valid_value(contrato_info.get("DÍAS DESTINO APROBADOS", ""), contrato_info.get("FDD", "")))

                                    col3, col4 = st.columns(2)
                                    index = 0

                                    for key, value in fields.items():
                                        if key == "Suitable Food":
                                            if value == "TRUE":
                                                display_value = "Yes"
                                            else:
                                                continue 
                                        else:
                                            if pd.notna(value) and str(value).strip() and str(value) != "0": 
                                                display_value = value
                                            else:
                                                continue 

                                        if index % 2 == 0:
                                            col3.write(f"**{key}:** {display_value}")
                                        else:
                                            col4.write(f"**{key}:** {display_value}")
                                        index += 1 

                                    # 🔹 Validar fecha de expiración
                                    if pd.notna(contrato_info['FECHA FIN FLETE']):
                                        fecha_fin = contrato_info['FECHA FIN FLETE']
                                        dias_restantes = (fecha_fin - hoy).days
                                        if dias_restantes <= 15:
                                            st.warning(f"⚠️ **This contract expires soon: {fecha_fin.date()}**")

                                    # 🔹 Generar la tabla de costos
                                    columnas_clave = ["ORIGEN", "FLETE", "DESTINO", "TOTAL FLETE Y ORIGEN", "HBL", "Switch", "TOTAL FLETE, ORIGEN Y DESTINO", "TOTAL FLETE, ORIGEN Y SWITCH O HBL"]
                                    contrato_rows_validos = contrato_rows.dropna(subset=columnas_clave, how="all")

                                    if not contrato_rows_validos.empty:
                                        tabla_pivot = contrato_rows_validos.pivot_table(
                                            index=[],
                                            columns="TIPO CONT",
                                            values=columnas_clave,
                                            aggfunc=lambda x: x.iloc[0] if not x.empty else "Pendiente",
                                            fill_value=pd.NA
                                        )

                                        if isinstance(tabla_pivot.columns, pd.MultiIndex):
                                            available_cargo_types = tabla_pivot.columns.get_level_values(1).unique().tolist()
                                        else:
                                            available_cargo_types = tabla_pivot.columns.unique().tolist()

                                        tabla_pivot.rename_axis("CONCEPTO", inplace=True)
                                        nuevo_orden =  ["ORIGEN", "FLETE", "DESTINO", "TOTAL FLETE Y ORIGEN", "HBL", "Switch", "TOTAL FLETE, ORIGEN Y DESTINO", "TOTAL FLETE, ORIGEN Y SWITCH O HBL"]
                                        tabla_pivot = tabla_pivot.reindex(nuevo_orden)
                                        tabla_pivot.index = tabla_pivot.index.map(lambda x: x.capitalize() if isinstance(x, str) else x)
                                        tabla_pivot.dropna(how="all", inplace=True)
                                        tabla_pivot = tabla_pivot.astype(str)

                                        tabla_pivot = tabla_pivot.loc[~(tabla_pivot.apply(lambda x: x.str.strip()).eq("").all(axis=1))]

                                        tabla_pivot.dropna(axis=1, how="all", inplace=True)

                                        st.table(tabla_pivot)

                                    notas = contrato_info.get("NOTAS", "")

                                    def capitalizar_notas(notas):
                                        lineas = notas.split("\n")
                                        lineas_transformadas = [
                                            linea.capitalize() if linea.isupper() else linea
                                            for linea in lineas
                                        ]
                                        return "\n".join(lineas_transformadas)

                                    notas_formateadas = capitalizar_notas(notas).replace("\n", "  \n")  
                                    st.markdown(f"**Notes:**  \n{notas_formateadas}")

                                    # 🔹 Botón para seleccionar contrato
                                    if st.button('Select', key=f"select_{linea}_{contrato_id}"):
                                        st.session_state["selected_contract"] = contrato_id
                                        st.session_state["selected_data"] = {
                                            "Commercial": name,
                                            "POL": p_origen,
                                            "POD": p_destino,
                                            "Contract ID": contrato_id,
                                            "Details": fields
                                        }
                                        select_options(contrato_id, available_cargo_types, tabla_pivot)

                        st.write("\n")
            else:
                st.warning("⚠️ There are not active contracts")

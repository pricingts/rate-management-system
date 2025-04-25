import streamlit as st
import pandas as pd
from services.utils import *
from datetime import datetime
import pytz
from services.write_pdf import generate_pdf
import math

colombia_timezone = pytz.timezone('America/Bogota')

def save_to_google_sheets(data, start_time):
    SPREADSHEET_ID = st.secrets['general']['time_sheet_id']
    SHEET_NAME = "SOLICITUD DE ANTICIPO"

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
                "Time", "Commercial", "Cliente", "Customer Name", "Customer Phone", "Customer Email", "Container Type", "Service Type",
                "Operation Type", "Reference", "Surcharges", "Total USD", "Total COP", "TRM", "Total en COP TRM"
            ]

            worksheet.append_row(headers)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("The specified Google Sheets document was not found.")
        return

    client = data["client"]
    customer_name = data["customer_name"]
    customer_phone = data["customer_phone"]
    customer_email = data["customer_email"]

    operation_type = data["operation_type"]
    reference = data["reference"]
    commercial = data["commercial"]

    trm = data["trm"]
    total_cop_trm = data["total_cop_trm"]

    container_list = data['container_type']
    containers = [
        '\n'.join(x) if isinstance(x, list) else x
        for x in container_list
    ]
    containers_str = '\n'.join(containers)

    transport_list = data['transport_type']
    transports = [
        '\n'.join(x) if isinstance(x, list) else x
        for x in transport_list
    ]
    transport_str = '\n'.join(transports)

    additional_surcharge_costs = []
    usd_total = 0.0
    cop_total = 0.0

    for container_type, surcharges in data["additional_surcharges"].items():
        for add_surcharge in surcharges:
            cost = add_surcharge['cost']
            currency = add_surcharge['currency']
            concept = add_surcharge['concept']
            additional_surcharge_costs.append(
                f"{container_type} - {concept}: ${cost:.2f} {currency}"
            )
            if currency == 'USD':
                usd_total += cost
            elif currency == 'COP':
                cop_total += cost

    additional_surcharge_costs_str = "\n".join(additional_surcharge_costs)

    st.session_state["end_time"] = datetime.now(pytz.utc).astimezone(colombia_timezone)
    end_time = st.session_state.get("end_time", None)
    if end_time is not None:
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
    else:
        st.error("Error: 'end_time' no fue asignado correctamente.")
        return

    row = [
        commercial, end_time_str, client, customer_name, customer_phone, customer_email, containers_str, 
        transport_str, operation_type, reference, additional_surcharge_costs_str, usd_total, cop_total, trm, total_cop_trm
    ]
    worksheet.append_row(row)

def show(role):
    if "client" not in st.session_state:
        st.session_state["client"] = None

    if "clients_list" not in st.session_state:
        st.session_state["clients_list"] = []

    if not st.session_state["clients_list"]:
        try:
            client_data = load_clients()
            st.session_state["clients_list"] = client_data if client_data else []
        except Exception as e:
            st.error(f"Error al cargar la lista de clientes: {e}")
            st.session_state["clients_list"] = []

    if st.session_state.get("start_time") is None:
        st.session_state["start_time"] = datetime.now(colombia_timezone)

    start_time = st.session_state["start_time"]
    clients_list = st.session_state.get("clients_list", [])

    col1, col2 = st.columns(2)

    commercial_op = [" ","Pedro Luis Bruges", "Andrés Consuegra", "Ivan Zuluaga", "Sharon Zuñiga",
            "Johnny Farah", "Felipe Hoyos", "Jorge Sánchez",
            "Irina Paternina", "Stephanie Bruges"]

    with col1:
        commercial = st.selectbox("Select Sales Rep*", commercial_op, key="commercial")
    with col2:
        no_solicitud = st.text_input("Operation Number (M)*", key="no_solicitud")

    with st.expander("**Client Information**",expanded=True):
        client = st.selectbox("Select your Client*", [" "] + ["+ Add New"] + clients_list, key="client")

        new_client_saved = st.session_state.get("new_client_saved", False)

        if client == "+ Add New":
            st.write("### Add a New Client")
            new_client_name = st.text_input("Enter the client's name:", key="new_client_name")

            if st.button("Save Client"):
                if new_client_name:
                    if new_client_name not in st.session_state["clients_list"]:
                        st.session_state["clients_list"].append(new_client_name)
                        st.session_state["client"] = new_client_name
                        st.session_state["new_client_saved"] = True
                        st.success(f"✅ Client '{new_client_name}' saved!")
                        st.rerun()
                    else:
                        st.warning(f"⚠️ Client '{new_client_name}' already exists in the list.")
                else:
                    st.error("⚠️ Please enter a valid client name.")

        col1, col2, col3 = st.columns(3)

        with col1:
            customer_name = st.text_input("Customer Name*", key="customer_name")
        with col2:
            customer_phone = st.text_input("Customer Phone", key="customer_phone")
        with col3:
            customer_email = st.text_input("Customer Email", key="customer_email")
    
    with st.expander("**Transport Information**", expanded=True):
        container_op = ["20' Dry Standard",
            "40' Dry Standard",
            "40' Dry High Cube",
            "Reefer 20'",
            "Reefer 40'",
            "Open Top 20'",
            "Open Top 40'",
            "Flat Rack 20'",
            "Flat Rack 40'"]

        container_type= st.multiselect("Select Container Type(s)*", container_op, key='container_type')
        col4, col5, col6 = st.columns(3)
        transp_op = ['Flete Internacional', 'Transporte Terrestre', 'Agenciamiento ']
        with col4:
            transport_type = st.multiselect("Select Service Type(s)*", transp_op, key="transport_type")
        with col5:
            operation_type = st.text_input("Operation Type*", key="operation_type")
        with col6:
            reference = st.text_input("Customer Reference", key="reference")

    with st.expander("**Surcharges**", expanded=True):

        if "additional_surcharges" not in st.session_state or not isinstance(st.session_state["additional_surcharges"], dict):
            st.session_state["additional_surcharges"] = {}

        def remove_surcharge(container, index):
            del st.session_state["additional_surcharges"][container][index]

        def add_surcharge(container):
            st.session_state["additional_surcharges"][container].append({"concept": "", "currency": "", "cost": 0.0})

        all_surcharges = []
        for cont in container_type:
            if cont not in st.session_state["additional_surcharges"]:
                st.session_state["additional_surcharges"][cont] = []

            all_surcharges.extend(st.session_state["additional_surcharges"][cont])

        currencies = {s["currency"] for s in all_surcharges if s["currency"]}

        need_trm = "USD" in currencies and "COP" in currencies

        if need_trm:
            trm = st.number_input("Enter TRM (USD to COP)*", min_value=0.0, step=0.01, key="trm")
        else:
            trm = None

        total = 0
        currency_total = "COP" if currencies == {"COP"} else "USD" if currencies == {"USD"} else "COP"

        for cont in container_type:
            st.write(f"**{cont}**")

            for i, surcharge in enumerate(st.session_state["additional_surcharges"][cont]):
                col1, col2, col3, col4 = st.columns([2.5, 1, 0.5, 0.5])

                with col1:
                    surcharge["concept"] = st.text_input(f"Concept*", surcharge["concept"], key=f'{cont}_concept_{i}')

                with col2:
                    surcharge["currency"] = st.selectbox(f"Currency*", ['USD', 'COP'], index=0 if surcharge["currency"] == "USD" else 1, key=f'{cont}_currency_{i}')

                with col3:
                    surcharge["cost"] = st.number_input(f"Cost*", min_value=0.0, step=0.01, value=surcharge["cost"], key=f'{cont}_cost_{i}')

                with col4:
                    st.write(" ")
                    st.write(" ")
                    st.button("❌", key=f'remove_{cont}_{i}', on_click=remove_surcharge, args=(cont, i))

                if surcharge["currency"] == "USD":
                    total += surcharge["cost"] * (trm if need_trm else 1)
                else:
                    total += surcharge["cost"]

            st.button(f"➕ Add Surcharges", key=f"add_{cont}", on_click=add_surcharge, args=(cont,))

        total_rounded = math.ceil(total * 100) / 100
        symbol = "$" if currency_total == "USD" else "$"
        suffix = "USD" if currency_total == "USD" else "COP"
        formatted_total = f"{symbol}{total_rounded:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {suffix}"
        st.markdown(f"### **Total: {formatted_total}**")

    request_data = {
        "no_solicitud": no_solicitud,
        "commercial": commercial,
        "client": st.session_state.get("client", client),
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": customer_email,
        "container_type": container_type,
        "transport_type": transport_type,
        "operation_type": operation_type,
        "reference": reference,
        "additional_surcharges": st.session_state["additional_surcharges"],
        "trm": trm,
        "total_cop_trm": formatted_total
    }

    if st.button('Send Information'):

        errors = validate_request_data(request_data)

        if errors:
            for error in errors:
                st.error(error)
        else:
            save_to_google_sheets(request_data, start_time)

            st.success("Information saved successfully!")

            client_normalized = st.session_state.get("client", client).strip().lower() if client else ""

            if client_normalized and all(c.strip().lower() != client_normalized for c in st.session_state["clients_list"]):
                sheet = client_gcp.open_by_key(time_sheet_id)
                worksheet = sheet.worksheet("clientes")
                worksheet.append_row([st.session_state.get("client", client)])
                st.session_state["clients_list"].append(client)
                st.session_state["client"] = None
                load_clients.clear()
                st.rerun()

            pdf_filename = generate_pdf(request_data)

            with open(pdf_filename, "rb") as f:
                pdf_bytes = f.read()

            st.download_button(
                label="Download PDF",
                data=pdf_bytes,
                file_name="Solicitud de Anticipo.pdf",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
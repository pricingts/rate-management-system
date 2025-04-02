import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread
from datetime import datetime

time_sheet_id = st.secrets["general"]["time_sheet_id"]

sheets_creds = Credentials.from_service_account_info(
        st.secrets["google_sheets_credentials"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )

sheets_service = build('sheets', 'v4', credentials=sheets_creds)

drive_creds = Credentials.from_service_account_info(
    st.secrets["google_drive_credentials"],
    scopes=["https://www.googleapis.com/auth/drive"]
)

drive_service = build('drive', 'v3', credentials=drive_creds)

client_gcp = gspread.authorize(sheets_creds)

@st.cache_data(ttl=3600)
def load_clients():
    sheet_name = "clientes"
    
    try:
        sheet = client_gcp.open_by_key(time_sheet_id)
        worksheet_list = [ws.title for ws in sheet.worksheets()]
        
        if sheet_name not in worksheet_list:
            return []

        worksheet = sheet.worksheet(sheet_name)
        clientes = worksheet.col_values(1)

        return clientes[1:]

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("No se encontró la hoja de cálculo con el ID proporcionado.")
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"No se encontró la pestaña '{sheet_name}' en la hoja de cálculo.")
    except Exception as e:
        st.error(f"Error al cargar los clientes desde Google Sheets: {e}")
    
    return []

def user_data(commercial):
    users = {
        "Sharon Zuñiga": {
            "name": "Sharon Zuñiga",
            "tel": "+57 (300) 510 0295",
            "position": "Business Development Manager",
            "email": "sales2@tradingsol.com"
        },
        "Irina Paternina": {
            "name": "Irina Paternina",
            "tel": "+57 (301) 3173340",
            "position": "Business Development Manager",
            "email": "sales1@tradingsol.com"
        },
        "Johnny Farah": {
            "name": "Johnny Farah",
            "tel": "+57 (301) 6671725",
            "position": "Manager of Americas",
            "email": "sales3@tradingsol.com"
        },
        "Jorge Sánchez": {
            "name": "Jorge Sánchez",
            "tel": "+57 (301) 7753510",
            "position": "Business Development Manager",
            "email": "sales4@tradingsol.com"
        },
        "Pedro Luis Bruges": {
            "name": "Pedro Luis Bruges",
            "tel": "+57 (304) 4969358",
            "position": "Business Development Manager",
            "email": "sales@tradingsol.com"
        },
        "Ivan Zuluaga": {
            "name": "Ivan Zuluaga",
            "tel": "+57 (300) 5734657",
            "position": "Business Development Manager",
            "email": "sales5@tradingsol.com"
        },
        "Andrés Consuegra": { 
            "name": "Andrés Consuegra",
            "tel": "+57 (301) 7542622",
            "position": "CEO",
            "email": "manager@tradingsol.com"
        },
        "Stephanie Bruges": {
            "name": "Stephanie Bruges",
            "tel": "+57 300 4657077",
            "position": "Business Development Specialist",
            "email": "bds@tradingsol.com"
        },
        "Catherine Silva": {
            "name": "Catherine Silva",
            "tel": "+57 304 4969351",
            "position": "Inside Sales",
            "email": "insidesales@tradingsol.com"
        }
    }

    return users.get(commercial, {"name": commercial, "position": "N/A", "tel": "N/A", "email": "N/A"})

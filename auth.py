import streamlit as st
from google_auth_st import add_auth

def user_data():
    user = st.session_state.email
    users = {
        "pricing@tradingsol.com": {
            "name": "Shadia Jaafar",
            "tel": "+57 12345678",
            "position": "Data Analyst",
            "email": "pricing@tradingsol.com"
        },
        "sales2@tradingsol.com": {
            "name": "Sharon Zuñiga",
            "tel": "+57 (300) 510 0295",
            "position": "Business Development Manager",
            "email": "sales2@tradingsol.com"
        },
        "sales1@tradingsol.com": {
            "name": "Irina Paternina",
            "tel": "+57 (301) 3173340",
            "position": "Business Development Manager",
            "email": "sales1@tradingsol.com"
        },
        "sales3@tradingsol.com": {
            "name": "Johnny Farah",
            "tel": "+57 (301) 6671725",
            "position": "Manager of Americas",
            "email": "sales3@tradingsol.com"
        },
        "sales4@tradingsol.com": {
            "name": "Jorge Sánchez",
            "tel": "+57 (301) 7753510",
            "position": "Business Development Manager",
            "email": "sales4@tradingsol.com"
        },
        "sales@tradingsol.com": {
            "name": "Pedro Luis Bruges",
            "tel": "+57 (304) 4969358",
            "position": "Business Development Manager",
            "email": "sales@tradingsol.com"
        },
        "sales5@tradingsol.com": {
            "name": "Ivan Zuluaga",
            "tel": "+57 (300) 5734657",
            "position": "Business Development Manager",
            "email": "sales5@tradingsol.com"
        },
        "manager@tradingsol.com": { 
            "name": "Andrés Consuegra",
            "tel": "+57 (301) 7542622",
            "position": "CEO",
            "email": "manager@tradingsol.com"
        },
        "bds@tradingsol.com": {
            "name": "Stephanie Bruges",
            "tel": "+57 300 4657077",
            "position": "Business Development Specialist",
            "email": "bds@tradingsol.com"
        },
        "insidesales@tradingsol.com": {
            "name": "Catherine Silva",
            "tel": "+57 304 4969351",
            "position": "Inside Sales",
            "email": "insidesales@tradingsol.com"
        }
    }

    return users.get(user, {"name": "Desconocido", "position": "N/A", "tel": "N/A", "email": user})



def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.warning("Please Login first")
        add_auth(login_sidebar=False)
        st.success("Welcome!")
        st.session_state.authenticated = True
        return True 

    return True

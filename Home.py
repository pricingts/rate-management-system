import streamlit as st
import pandas as pd
from src.services.auth import check_authentication
from collections import defaultdict

st.set_page_config(page_title="Rate Management System", layout="wide")

def identity_role(email):
    role_mapping = defaultdict(list)

    roles = {
        "commercial": [
            "sales2", "sales1", "sales3", "sales4", "sales5", "sales6", "bds", "insidesales"
        ],
        "pricing": [
            "pricing2", "pricing8", "pricing6", "pricing10", "pricing11", "customer9"
        ],
        "admin": [
            "manager", "jsanchez", "pricing2", "pricing", "manager"
        ],
        "scrap_team": [
            "bds", "insidesales", "sales", "pricing3", "pricing6"
        ],
        "ground": [
            "ground", "customer5", "ground1"
        ],
        "inside_sales": [
            "pricing7", "traffic2", "customer3"
        ]
    }

    domain_variants = ["@tradingsolutions.com", "@tradingsol.com"]

    email_to_role = {}
    for role, usernames in roles.items():
        for username in usernames:
            for domain in domain_variants:
                full_email = f"{username}{domain}"
                email_to_role[full_email] = role

    return email_to_role.get(email, None)


@st.dialog("Warning", width="large")
def non_identiy():
    st.write("Dear user, it appears that you do not have an assigned role on the platform. This might restrict your access to certain features. Please contact the support team to have the appropriate role assigned. Thank you!")
    st.write("pricing@tradingsol.com")

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.image("resources/images/logo_trading.png", width=800)

check_authentication()
role = identity_role(st.experimental_user.email)

if role is None:
    non_identiy()
else:
    user = st.experimental_user.name

    if role in ["commercial", "admin"]:
        with st.sidebar:
            page = st.radio("Go to", ["Home", "Contracts Management", "Your Quotations", "New Request", "Download Payment Request"])

        if page == "Contracts Management":
            import src.views.Contracts_Management as cm
            cm.show(role)

        elif page == "Your Quotations":
            import src.views.Your_Quotations as pricing 
            pricing.show(role)

        elif page == "New Request":
            import src.views.New_Request as quotes
            quotes.show(role)

        elif page == "Download Payment Request":
            import src.views.Payment_Request as pay
            pay.show(role)

    elif role in ["pricing", "ground", "inside_sales"]:
        with st.sidebar:
            page = st.radio("Go to", ["Home", "Contracts Management", "Your Quotations", "Download Payment Request"])

        if page == "Contracts Management":
            import src.views.Contracts_Management as cm
            cm.show(role)

        elif page == "Your Quotations":
            import src.views.Your_Quotations as pricing 
            pricing.show(role)

        elif page == "Download Payment Request":
            import src.views.Payment_Request as pay 
            pay.show(role)

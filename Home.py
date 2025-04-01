import streamlit as st
import pandas as pd
from src.services.auth import check_authentication

st.set_page_config(page_title="Rate Management System", layout="wide")

def identity_role(email):
    commercial = [
        "sales2@tradingsol.com", "sales1@tradingsol.com", "sales3@tradingsol.com",
        "sales4@tradingsol.com", "sales@tradingsol.com", "sales5@tradingsol.com",
        "bds@tradingsol.com", "insidesales@tradingsol.com"
    ]
    pricing = [
        "pricing2@tradingsol.com", "pricing8@tradingsol.com",
        "pricing6@tradingsol.com", "pricing10@tradingsol.com", "pricing11@tradingsol.com",
        "customer9@tradingsol.com",
    ]
    ground = [
        "ground@tradingsol.com", "customer5@tradingsol.com", "ground1@tradingsol.com"
    ]
    admin = [
        "manager@tradingsol.com", "pricing10@tradingsol.com", "pricing2@tradingsol.com", "pricing@tradingsol.com"
    ]

    if email in commercial:
        return "commercial"
    elif email in pricing:
        return "pricing"
    elif email in ground:
        return "ground"
    elif email in admin:
        return "admin"
    else:
        return None

@st.dialog("Warning", width="large")
def non_identiy():
    st.write("Dear user, it appears that you do not have an assigned role on the platform. This might restrict your access to certain features. Please contact the support team to have the appropriate role assigned. Thank you!")
    st.write("datasupport@tradingsol.com")

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
            page = st.radio("Go to", ["Home", "Contracts Management", "Your Quotations", "New Request"])

        if page == "Contracts Management":
            import src.views.Contracts_Management as cm
            cm.show(role)

        elif page == "Your Quotations":
            import src.views.Your_Quotations as pricing 
            pricing.show(role)

        elif page == "New Request":
            import src.views.New_Request as quotes
            quotes.show()

    elif role in ["pricing", "ground"]:
        with st.sidebar:
            page = st.radio("Go to", ["Home", "Contracts Management", "Your Quotations"])

        if page == "Contracts Management":
            import src.views.Contracts_Management as cm
            cm.show(role)

        elif page == "Your Quotations":
            import src.views.Your_Quotations as pricing 
            pricing.show(role)

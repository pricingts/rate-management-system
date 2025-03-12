import streamlit as st
import pandas as pd
from auth import check_authentication

st.set_page_config(page_title="Rate Management System", layout="wide")

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.image("images/logo_trading.png", width=800)

if not check_authentication():
    st.stop() 

user = st.session_state.email

with st.sidebar:
    page = st.radio("Go to", ["Home", "Contracts Management", "Your Quotations", "Request your Quotes"])

if page == "Contracts Management":
    import views.Contracts_Management as cm
    cm.show(user)

elif page == "Your Quotations":
    import views.Your_Quotations as pricing 
    pricing.show(user)

elif page == "Request your Quotes":
    import views.Request_your_Quotes as quotes
    quotes.show(user)
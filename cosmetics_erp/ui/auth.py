from __future__ import annotations

import hmac
import os

import streamlit as st


def configured_password() -> str | None:
    """Password from Streamlit secrets or the COSMETICS_APP_PASSWORD environment variable.

    When neither is set the app runs without a gate, which is fine for local use only.
    """
    try:
        secret = st.secrets.get("APP_PASSWORD")
    except Exception:
        secret = None
    return secret or os.environ.get("COSMETICS_APP_PASSWORD") or None


def require_login() -> None:
    """Stop the script until the viewer enters the configured password."""
    expected = configured_password()
    if not expected or st.session_state.get("authenticated"):
        return

    st.markdown("<div class='clean-header'><h2 style='margin:0;'>Cosmetics ERP</h2></div>", unsafe_allow_html=True)
    st.caption("הזן/י סיסמה כדי להמשיך · Enter the password to continue")
    with st.form("login_form"):
        entered = st.text_input("סיסמה / Password", type="password")
        submitted = st.form_submit_button("כניסה / Sign in", type="primary")
    if submitted:
        if hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8")):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("סיסמה שגויה · Incorrect password")
    st.stop()

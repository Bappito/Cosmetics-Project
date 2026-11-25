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


_LOGIN_TEXT = {
    "he": {
        "prompt": "הזן/י שם וסיסמה כדי להמשיך",
        "name": "השם שלך (לתרחישים האישיים)",
        "name_missing": "יש להזין שם.",
        "password": "סיסמה",
        "submit": "כניסה",
        "wrong": "סיסמה שגויה",
    },
    "en": {
        "prompt": "Enter your name and the password to continue",
        "name": "Your name (for your personal scenarios)",
        "name_missing": "Enter a name.",
        "password": "Password",
        "submit": "Sign in",
        "wrong": "Incorrect password",
    },
}


def require_login() -> None:
    """Stop the script until the viewer enters the password (when one is set) and a name.

    The name keys personal scenarios. It is not a secure account: anyone who knows the
    password can type any name.
    """
    expected = configured_password()
    if st.session_state.get("authenticated") and st.session_state.get("user_name"):
        return

    is_he = st.session_state.get("lang", "he") == "he"
    text = _LOGIN_TEXT["he" if is_he else "en"]
    st.markdown("<div class='clean-header'><h2 style='margin:0;'>Cosmetics ERP</h2></div>", unsafe_allow_html=True)
    st.caption(text["prompt"])
    with st.form("login_form"):
        name = st.text_input(text["name"], value=st.session_state.get("user_name", ""))
        entered = st.text_input(text["password"], type="password") if expected else ""
        submitted = st.form_submit_button(text["submit"], type="primary")
    if submitted:
        if not name.strip():
            st.error(text["name_missing"])
        elif expected and not hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8")):
            st.error(text["wrong"])
        else:
            st.session_state["authenticated"] = True
            st.session_state["user_name"] = name.strip()[:60]
            st.rerun()
    st.stop()

"""Interface strings for the page chrome (navigation, login, buttons).

Screen content uses ``cosmetics_erp.config.Localization`` so the wording matches the Streamlit app.
"""

UI = {
    "he": {
        "app_name": "Cosmetics ERP",
        "logout": "יציאה",
        "soon": "בקרוב",
        "username": "שם משתמש",
        "password": "סיסמה",
        "sign_in": "כניסה",
        "login_title": "כניסה למערכת",
        "login_hint": "הזינו שם משתמש וסיסמה כדי להמשיך.",
        "denied_title": "אין הרשאה",
        "denied_text": "אין לך הרשאה לצפות במסך הזה. פנה/י למנהל המערכת.",
        "errors": "שם המשתמש או הסיסמה שגויים.",
    },
    "en": {
        "app_name": "Cosmetics ERP",
        "logout": "Log out",
        "soon": "coming soon",
        "username": "Username",
        "password": "Password",
        "sign_in": "Sign in",
        "login_title": "Sign in",
        "login_hint": "Enter your username and password to continue.",
        "denied_title": "Access denied",
        "denied_text": "You do not have permission to view this screen. Ask an administrator.",
        "errors": "Incorrect username or password.",
    },
}

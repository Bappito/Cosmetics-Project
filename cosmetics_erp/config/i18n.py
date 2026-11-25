from __future__ import annotations

WH_NAMES = {
    "he": {
        "WH_RAW": "מחסן חומר גלם",
        "WH_BULK": "מחסן בלקים (חומר מוכן)",
        "WH_COLOR": "מחסן צבעים",
        "WH_PACK": "מחסן מלאי אריזות",
        "WH_LINE": "קו ייצור",
        "WH_QA": "מחסן איכות",
        "WH_FG": "מחסן תצורה מוכנה",
        "WH_VENDOR": "מחסן ספקים",
        "WH_SCRAP": "מחסן חומרה פגומה"
    },
    "en": {
        "WH_RAW": "Raw Materials WH",
        "WH_BULK": "Bulks (Ready Material) WH",
        "WH_COLOR": "Colours WH",
        "WH_PACK": "Packaging Stock WH",
        "WH_LINE": "Production Line",
        "WH_QA": "Quality Assurance WH",
        "WH_FG": "Finished Goods WH",
        "WH_VENDOR": "Vendors WH",
        "WH_SCRAP": "Defective / Scrap WH"
    }
}

TYPE_NAMES = {
    "he": {
        "RAW": "חומר גלם",
        "BULK": "בלק (חומר מוכן)",
        "PKG": "אריזה (בקבוק/מכסה/מתז/מדבקה)",
        "FG": "מוצר סופי ארוז"
    },
    "en": {
        "RAW": "Raw Material",
        "BULK": "Bulk (Ready Formula)",
        "PKG": "Packaging (Bottle/Cap/Pump/Label)",
        "FG": "Finished Packaged Product"
    }
}

WH_TO_KEY = {name: key for names in WH_NAMES.values() for key, name in names.items()}
TYPE_TO_KEY = {name: key for names in TYPE_NAMES.values() for key, name in names.items()}

UI_TEXTS = {
    "he": {
        "dir": "rtl", "align": "right",
        "nav_hdr": "תפריט ERP",
        "nav_inventory": "מלאי ורכש",
        "nav_planning": "תכנון וייצור",
        "nav_operations": "פעולות",
        "nav_overview": "סקירה",
        "m_bom": "עצי מוצר (BOM)",
        "m_audit": "יומן שינויים",
        "m_dash": "לוח בקרה",
        "m_inv": "מחסנים (מלאי, תפוגה ורכש)",
        "m_mrp": "תכנון רכש (MRP)",
        "m_sim_prod": "1. סימולטור קו ייצור",
        "m_sim_pack": "2. סימולטור אריזה",
        "m_sim_work": "3. סימולטור עבודה מסכם",
        "m_wh": "ניהול הזמנות רכש (PO) ו-SAP",
        "m_batch": "מרשם אצוות ועקיבות (FEFO)",
        "m_ai": "סוכן פקודות מהיר",
        "lang_btn": "EN | English",
        "unit_lbl": "יחידת משקל:",
        "kg": "ק\"ג (kg)", "g": "גרם (g)"
    },
    "en": {
        "dir": "ltr", "align": "left",
        "nav_hdr": "ERP Menu",
        "nav_inventory": "Inventory & Purchasing",
        "nav_planning": "Planning & Production",
        "nav_operations": "Operations",
        "nav_overview": "Overview",
        "m_bom": "Product trees (BOM)",
        "m_audit": "Change log",
        "m_dash": "Dashboard",
        "m_inv": "Warehouses (Stock, Expiry & PO)",
        "m_mrp": "Purchase Planning (MRP)",
        "m_sim_prod": "1. Production Line Simulator",
        "m_sim_pack": "2. Packaging Simulator",
        "m_sim_work": "3. Master Work Simulator",
        "m_wh": "Purchase Orders (PO) & SAP",
        "m_batch": "Batches & Traceability (FEFO)",
        "m_ai": "Quick Command Agent",
        "lang_btn": "עב | עברית",
        "unit_lbl": "Weight Unit:",
        "kg": "kg", "g": "g"
    }
}

def build_nav_items(ui: dict[str, str]) -> list[tuple[str, str, str, str]]:
    return [
        (ui["nav_overview"], "dash", ":material/dashboard:", ui["m_dash"]),
        (ui["nav_inventory"], "inv", ":material/warehouse:", ui["m_inv"]),
        (ui["nav_inventory"], "wh", ":material/local_shipping:", ui["m_wh"]),
        (ui["nav_inventory"], "mrp", ":material/event_repeat:", ui["m_mrp"]),
        (ui["nav_inventory"], "batch", ":material/qr_code_2:", ui["m_batch"]),
        (ui["nav_planning"], "bom", ":material/account_tree:", ui["m_bom"]),
        (ui["nav_planning"], "sim_prod", ":material/precision_manufacturing:", ui["m_sim_prod"]),
        (ui["nav_planning"], "sim_pack", ":material/inventory_2:", ui["m_sim_pack"]),
        (ui["nav_planning"], "sim_work", ":material/analytics:", ui["m_sim_work"]),
        (ui["nav_operations"], "ai", ":material/terminal:", ui["m_ai"]),
        (ui["nav_operations"], "audit", ":material/history:", ui["m_audit"]),
    ]

HE_MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]


def build_plan_periods(is_he: bool, plan_start) -> list[tuple[str, str, str]]:
    """Eight weeks starting at plan_start, labelled with the real dates."""
    from datetime import timedelta

    periods = []
    for i in range(8):
        start = plan_start + timedelta(days=7 * i)
        end = start + timedelta(days=6)
        if is_he:
            month = f"{HE_MONTHS[start.month - 1]} {start.year}"
            label = f"שבוע {i + 1}"
        else:
            month = start.strftime("%b %Y")
            label = f"Week {i + 1}"
        periods.append((f"W{i + 1}", month, label))
    return periods


class Localization:
    def __init__(self, lang: str, plan_start=None) -> None:
        from datetime import date, timedelta

        if plan_start is None:
            today = date.today()
            plan_start = today - timedelta(days=(today.weekday() + 1) % 7)
        if lang not in UI_TEXTS:
            raise ValueError(f"Unsupported language: {lang}")
        self.lang = lang
        self.is_he = lang == "he"
        self.ui = UI_TEXTS[lang]
        self.nav_items = build_nav_items(self.ui)
        self.plan_start = plan_start
        self.plan_periods = build_plan_periods(self.is_he, plan_start)

    def translate(self, he_txt: str, en_txt: str) -> str:
        return he_txt if self.is_he else en_txt

    def translate_warehouse(self, value: str) -> str:
        key = WH_TO_KEY.get(value, value)
        return WH_NAMES[self.lang].get(key, value)

    def translate_item_type(self, value: str) -> str:
        key = TYPE_TO_KEY.get(value, value)
        return TYPE_NAMES[self.lang].get(key, value)

from __future__ import annotations

WH_NAMES = {
    "he": {
        "WH_RAW": "מחסן חומר גלם",
        "WH_BULK": "מחסן בלקים (חומר מוכן)",
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
        (ui["nav_planning"], "sim_prod", ":material/precision_manufacturing:", ui["m_sim_prod"]),
        (ui["nav_planning"], "sim_pack", ":material/inventory_2:", ui["m_sim_pack"]),
        (ui["nav_planning"], "sim_work", ":material/analytics:", ui["m_sim_work"]),
        (ui["nav_operations"], "ai", ":material/terminal:", ui["m_ai"]),
    ]

def build_plan_periods(is_he: bool) -> list[tuple[str, str, str]]:
    return [
        ("W1", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 1 (15-21/11)" if is_he else "Week 1 (Nov 15)"),
        ("W2", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 2 (22-28/11)" if is_he else "Week 2 (Nov 22)"),
        ("W3", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 3 (29/11-05/12)" if is_he else "Week 3 (Nov 29)"),
        ("W4", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 4 (06-12/12)" if is_he else "Week 4 (Dec 06)"),
        ("W5", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 5 (13-19/12)" if is_he else "Week 5 (Dec 13)"),
        ("W6", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 6 (20-26/12)" if is_he else "Week 6 (Dec 20)"),
        ("W7", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 7 (27/12-02/01)" if is_he else "Week 7 (Dec 27)"),
        ("W8", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 8 (03-09/01)" if is_he else "Week 8 (Jan 03)"),
    ]

class Localization:
    def __init__(self, lang: str) -> None:
        if lang not in UI_TEXTS:
            raise ValueError(f"Unsupported language: {lang}")
        self.lang = lang
        self.is_he = lang == "he"
        self.ui = UI_TEXTS[lang]
        self.nav_items = build_nav_items(self.ui)
        self.plan_periods = build_plan_periods(self.is_he)

    def translate(self, he_txt: str, en_txt: str) -> str:
        return he_txt if self.is_he else en_txt

    def translate_warehouse(self, value: str) -> str:
        key = WH_TO_KEY.get(value, value)
        return WH_NAMES[self.lang].get(key, value)

    def translate_item_type(self, value: str) -> str:
        key = TYPE_TO_KEY.get(value, value)
        return TYPE_NAMES[self.lang].get(key, value)

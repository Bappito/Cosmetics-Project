from cosmetics_erp.text_language import localize_text


def test_two_language_name_shows_only_the_page_language():
    name = "חמאת שיאה אורגנית / Shea Butter"
    assert localize_text(name, "he") == "חמאת שיאה אורגנית"
    assert localize_text(name, "en") == "Shea Butter"


def test_single_language_names_are_unchanged():
    assert localize_text("צבע שיער 4.0 חום (דוגמה)", "en") == "צבע שיער 4.0 חום (דוגמה)"
    assert localize_text("KIT,DIGITAL NAVIGATION SYSTEM", "he") == "KIT,DIGITAL NAVIGATION SYSTEM"


def test_references_and_codes_are_not_changed():
    assert localize_text("PROD 5001 / LOT-1", "he") == "PROD 5001 / LOT-1"
    assert localize_text("1001-B", "en") == "1001-B"

from .strings import UI


def language(request):
    """Adds the current language, text direction and UI strings to every template."""
    lang = request.session.get("lang", "he") if hasattr(request, "session") else "he"
    if lang not in UI:
        lang = "he"
    return {
        "lang": lang,
        "dir": "rtl" if lang == "he" else "ltr",
        "ui": UI[lang],
        "other_lang": "en" if lang == "he" else "he",
    }

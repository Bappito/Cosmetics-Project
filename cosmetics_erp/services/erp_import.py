from __future__ import annotations

"""Read ERP exports (SAP, Priority, or any CSV/Excel) and turn them into validated rows.

Nothing here writes to the database. The UI shows the validated rows for review
and only then applies them, after a stock backup.
"""

from io import BytesIO

import pandas as pd

# Common export headers used to pre-select columns. These are guesses; confirm them
# against a real export from your system before relying on them.
COLUMN_GUESSES = {
    "sku": ["MATNR", "PARTNAME", "PART", "SKU", "מקט"],
    "qty": ["LABST", "MENGE", "BALANCE", "QUANT", "QTY", "כמות"],
    "batch": ["CHARG", "LOTNAME", "BATCH", "אצווה"],
    "expiry": ["VFDAT", "EXPIRYDATE", "EXPIRY", "תפוגה"],
    "po_number": ["EBELN", "ORDNAME", "PO", "PO_NUMBER", "הזמנה"],
    "supplier": ["LIFNR", "SUPNAME", "SUPPLIER", "ספק"],
    "eta": ["EINDT", "DUEDATE", "ETA", "תאריך הגעה"],
}


def read_table(file_name: str, data: bytes) -> pd.DataFrame:
    lowered = file_name.lower()
    if lowered.endswith(".csv"):
        for encoding in ("utf-8-sig", "cp1255", "latin-1"):
            try:
                df = pd.read_csv(BytesIO(data), dtype=str, encoding=encoding, sep=None, engine="python")
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode the CSV file.")
    elif lowered.endswith((".xlsx", ".xls")):
        df = pd.read_excel(BytesIO(data), dtype=str)
    else:
        raise ValueError("Only .csv, .xlsx, and .xls files are supported.")
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all").reset_index(drop=True)


def guess_column(columns: list[str], field: str) -> str | None:
    by_upper = {c.upper(): c for c in columns}
    for candidate in COLUMN_GUESSES.get(field, []):
        if candidate.upper() in by_upper:
            return by_upper[candidate.upper()]
    return None


def _numbers(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def build_stock_rows(df: pd.DataFrame, mapping: dict[str, str], known_skus: set[str], weight_skus: set[str], factor: float):
    """Return (rows, errors). rows have sku and counted (already in base units: grams or units).

    factor converts the file's quantity to grams for weight items (1000 when the file uses kg); unit items are unchanged.
    Duplicate SKUs in the file are summed, since ERP exports often split one SKU by batch.
    """
    errors: list[str] = []
    sku = df[mapping["sku"]].astype(str).str.strip()
    qty = _numbers(df[mapping["qty"]])
    bad_rows = sku.eq("") | qty.isna() | (qty < 0)
    if bad_rows.any():
        rows = ", ".join(str(i + 2) for i in df.index[bad_rows][:10])
        errors.append(f"שורות עם מק\"ט חסר או כמות לא תקינה / Rows with missing SKU or invalid quantity: {rows}")
    unknown = sorted(set(sku[~sku.eq("") & ~sku.isin(known_skus)]))
    if unknown:
        errors.append(f"מק\"טים שלא קיימים בקטלוג / SKUs not in catalog: {', '.join(unknown)}")
    valid =df[~bad_rows & sku.isin(known_skus)]
    scale = sku[valid.index].isin(weight_skus).map({True: factor, False: 1.0})
    grouped = pd.DataFrame({"sku": sku[valid.index], "qty": qty[valid.index] * scale}).groupby("sku", as_index=False)["qty"].sum()
    grouped = grouped.rename(columns={"qty": "counted"})
    return grouped, errors


def build_po_rows(df: pd.DataFrame, mapping: dict[str, str], known_skus: set[str], weight_skus: set[str], factor: float):
    """Return (rows, errors). rows are dicts ready for PurchaseOrders."""
    errors: list[str] = []
    po_number = df[mapping["po_number"]].astype(str).str.strip()
    sku = df[mapping["sku"]].astype(str).str.strip()
    qty = _numbers(df[mapping["qty"]])
    eta = pd.to_datetime(df[mapping["eta"]], dayfirst=True, errors="coerce") if mapping.get("eta") else pd.Series(pd.NaT, index=df.index)
    supplier = df[mapping["supplier"]].fillna("").astype(str).str.strip() if mapping.get("supplier") else pd.Series("", index=df.index)

    bad = po_number.eq("") | sku.eq("") | qty.isna() | (qty < 0)
    if bad.any():
        rows = ", ".join(str(i + 2) for i in df.index[bad][:10])
        errors.append(f"שורות עם מספר PO, מק\"ט או כמות לא תקינים / Rows with invalid PO number, SKU or quantity: {rows}")
    unknown = sorted(set(sku[~sku.eq("") & ~sku.isin(known_skus)]))
    if unknown:
        errors.append(f"מק\"טים שלא קיימים בקטלוג / SKUs not in catalog: {', '.join(unknown)}")
    if mapping.get("eta") and eta[~bad].isna().any():
        errors.append("יש תאריכי הגעה (ETA) שאינם תקינים. / Some ETA dates are not valid.")

    rows = []
    for idx in df.index[~bad & sku.isin(known_skus)]:
        eta_value = eta[idx]
        rows.append({
            "po_number": po_number[idx],
            "sku": sku[idx],
            "supplier": supplier[idx],
            "qty_base": float(qty[idx]) * (factor if sku[idx] in weight_skus else 1.0),
            "eta": "" if pd.isna(eta_value) else eta_value.strftime("%Y-%m-%d"),
        })
    return rows, errors

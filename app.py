from functools import partial

import streamlit as st

from cosmetics_erp.config import CLOSED_PO_STATUSES, Localization
from cosmetics_erp.db import get_connection, init_db
from cosmetics_erp.services.backups import BackupService
from cosmetics_erp.services.inventory import InventoryService
from cosmetics_erp.services.planning import PlanningService
from cosmetics_erp.ui.components import UIComponents
from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import format_value
from cosmetics_erp.ui.navigation import (
    initialize_session_state,
    render_language_toggle,
    render_sidebar,
)
from cosmetics_erp.ui.pages import batches, inventory, master_work, packaging, production, purchase_orders, quick_command
from cosmetics_erp.ui.styles import inject_stylesheet

# 2026-11-20

st.set_page_config(
    page_title="Cosmetics ERP",
    layout="wide",
    page_icon=":material/science:",
    initial_sidebar_state="expanded"
)

initialize_session_state()

lang = st.session_state.lang
is_collapsed = st.session_state.nav_collapsed

i18n = Localization(lang)
is_he = i18n.is_he
UI = i18n.ui
NAV_ITEMS = i18n.nav_items
PLAN_PERIODS = i18n.plan_periods
L = i18n.translate
planning = PlanningService(PLAN_PERIODS, L)
parse_date = planning.parse_date
eta_to_week = planning.eta_to_week
eta_week_label = planning.eta_week_label

inject_stylesheet(UI, is_collapsed)

init_db()
conn = get_connection()

active_page, use_kg = render_sidebar(UI, NAV_ITEMS, is_collapsed)
w_factor = 1000.0 if use_kg else 1.0
w_label = ("ק\"ג" if is_he else "kg") if use_kg else ("גרם" if is_he else "g")
u_label = "יח'" if is_he else "u"

fmt_val = partial(
    format_value,
    use_kg=use_kg,
    w_factor=w_factor,
    w_label=w_label,
    u_label=u_label,
)

render_language_toggle(UI)

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

# Initialize app-scoped services and shared UI components.

inventory_service = InventoryService(conn, L, parse_date, eta_to_week)
get_incoming_map = inventory_service.get_incoming_map
get_sku_expiry_summary = inventory_service.get_sku_expiry_summary
batch_col = inventory_service.batch_col
plan_fefo = inventory_service.plan_fefo
apply_picks = inventory_service.apply_picks
add_batch = inventory_service.add_batch
log_move = inventory_service.log_move
log_consumption = inventory_service.log_consumption
gen_batch_no = inventory_service.gen_batch_no
reconcile_batches = inventory_service.reconcile_batches
trace_chain = inventory_service.trace_chain

backup_service = BackupService(conn)
push_backup = backup_service.push_backup
last_backup = backup_service.last_backup
undo_last = backup_service.undo_last

components = UIComponents(
    translate=L,
    is_he=is_he,
    unit_label=u_label,
    plan_periods=PLAN_PERIODS,
    conn=conn,
    push_backup=push_backup,
    last_backup=last_backup,
    undo_backup=undo_last,
    get_incoming_map=get_incoming_map,
    format_value=fmt_val,
)
render_undo_button = components.render_undo_button
render_quick_planner = components.render_quick_planner
render_where_used_simulator = components.render_where_used_simulator

# Render the selected screen with its shared dependencies.
page_context = PageContext(
    CLOSED_PO_STATUSES=CLOSED_PO_STATUSES,
    L=L,
    PLAN_PERIODS=PLAN_PERIODS,
    UI=UI,
    add_batch=add_batch,
    apply_picks=apply_picks,
    conn=conn,
    eta_week_label=eta_week_label,
    fmt_val=fmt_val,
    gen_batch_no=gen_batch_no,
    get_incoming_map=get_incoming_map,
    get_sku_expiry_summary=get_sku_expiry_summary,
    is_he=is_he,
    log_consumption=log_consumption,
    log_move=log_move,
    parse_date=parse_date,
    plan_fefo=plan_fefo,
    push_backup=push_backup,
    reconcile_batches=reconcile_batches,
    render_quick_planner=render_quick_planner,
    render_undo_button=render_undo_button,
    render_where_used_simulator=render_where_used_simulator,
    trace_chain=trace_chain,
    u_label=u_label,
    w_factor=w_factor,
    w_label=w_label
)
page_renderers = {
    "inv": inventory.render,
    "sim_prod": production.render,
    "sim_pack": packaging.render,
    "sim_work": master_work.render,
    "wh": purchase_orders.render,
    "batch": batches.render,
    "ai": quick_command.render
}
page_renderers[active_page](page_context)

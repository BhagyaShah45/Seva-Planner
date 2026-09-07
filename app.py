import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from urllib.parse import quote
import re

st.set_page_config(
    page_title="Seva Planner",
    page_icon="🙏",
    layout="wide",
    initial_sidebar_state="expanded",
)

DAYS = [
    ("Day 1", "2026-09-08"),
    ("Day 2", "2026-09-09"),
    ("Day 3", "2026-09-10"),
    ("Day 4", "2026-09-11"),
    ("Day 5", "2026-09-12"),
    ("Day 6", "2026-09-13"),
    ("Day 7", "2026-09-14"),
    ("Day 8", "2026-09-15"),
]

DAY_COLORS = [
    "#E2F0D9", "#DDEBF7", "#FFF2CC", "#FCE4D6",
    "#E4DFEC", "#D9EAD3", "#D0E0E3", "#F4CCCC"
]

MEMBER_COLS = [
    "Building", "Flat", "Name", "Age", "Address",
    "Contact 1", "Contact 2", "Contact 3"
]
SEVA_COLS = [
    "Date", "Day", "Time", "Building", "Flat", "Member / Household",
    "Sevarthi 1", "Sevarthi 2", "Sevarthi 3", "Status", "Notes"
]

def clean_phone(x):
    if pd.isna(x):
        return ""
    return re.sub(r"[^0-9+]", "", str(x))

def standardize_building(x):
    x = str(x).strip()
    if x.lower() in {"samet shikhar", "samet shikhar mahal"}:
        return "Samet Shikhar Mahal"
    return x

@st.cache_resource(ttl=300)
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def load_data():
    client = get_gspread_client()
    spreadsheet_name = st.secrets["google_sheet"]["spreadsheet_name"]
    sh = client.open(spreadsheet_name)

    def get_ws(name):
        try:
            return sh.worksheet(name)
        except gspread.WorksheetNotFound:
            return sh.add_worksheet(title=name, rows=2000, cols=20)

    members_ws = get_ws("Members")
    seva_ws = get_ws("Seva")

    members = pd.DataFrame(members_ws.get_all_records())
    seva = pd.DataFrame(seva_ws.get_all_records())

    for c in MEMBER_COLS:
        if c not in members.columns:
            members[c] = ""
    members = members[MEMBER_COLS].copy()

    for c in SEVA_COLS:
        if c not in seva.columns:
            seva[c] = ""
    seva = seva[SEVA_COLS].copy()

    if not members.empty:
        members["Building"] = members["Building"].map(standardize_building)
        members["Name"] = members["Name"].astype(str).str.strip()
    if not seva.empty:
        seva["Building"] = seva["Building"].map(standardize_building)
        seva["Date"] = seva["Date"].astype(str)

    return members, seva, members_ws, seva_ws

def refresh():
    load_data.clear()
    st.rerun()

def ensure_headers(ws, headers):
    current = ws.row_values(1)
    if current != headers:
        ws.update("A1", [headers])

def append_member(member_ws, member):
    ensure_headers(member_ws, MEMBER_COLS)
    member_ws.append_row([member.get(c, "") for c in MEMBER_COLS], value_input_option="USER_ENTERED")

def append_seva_rows(seva_ws, rows):
    ensure_headers(seva_ws, SEVA_COLS)
    if rows:
        seva_ws.append_rows(rows, value_input_option="USER_ENTERED")

def maps_url(address):
    return "https://www.google.com/maps/search/?api=1&query=" + quote(address)

def tel_link(phone):
    return "tel:" + clean_phone(phone)

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.8rem;}
.seva-card {
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 10px;
    border: 1px solid #ddd;
}
.small {font-size: 0.85rem; color: #666;}
</style>
""", unsafe_allow_html=True)

st.title("🙏 Seva Planner")
st.caption("Home Seva management connected to Google Sheets")

try:
    members, seva, members_ws, seva_ws = load_data()
except Exception as e:
    st.error("Google Sheets connection could not be loaded.")
    st.code(str(e))
    st.info("Check .streamlit/secrets.toml and make sure the Google Sheet is shared with the service-account email.")
    st.stop()

# Sidebar
st.sidebar.header("Filters")

today = date.today().isoformat()
default_day_index = 0
for i, (_, d) in enumerate(DAYS):
    if d == today:
        default_day_index = i

day_options = ["All Days"] + [f"{d} — {pd.to_datetime(dt).strftime('%d %b')}" for d, dt in DAYS]
selected_day = st.sidebar.selectbox("Seva Day", day_options, index=default_day_index + 1 if today in [x[1] for x in DAYS] else 0)

building_options = ["All Buildings"] + sorted([x for x in members["Building"].dropna().unique() if str(x).strip()])
selected_building = st.sidebar.selectbox("Building", building_options)

names = sorted([x for x in members["Name"].dropna().unique() if str(x).strip()])
selected_sevarthi = st.sidebar.text_input("Search Sevarthi", placeholder="Type Sevarthi name")

search = st.sidebar.text_input("Search Member / Flat", placeholder="Name, flat or address")
status_options = ["All"] + sorted([x for x in seva["Status"].dropna().astype(str).unique() if x.strip()])
selected_status = st.sidebar.selectbox("Seva Status", status_options)

if st.sidebar.button("🔄 Refresh Google Sheet", use_container_width=True):
    refresh()

# KPIs
total_members = len(members[members["Name"].astype(str).str.strip() != ""])
total_buildings = members.loc[members["Building"].astype(str).str.strip() != "", "Building"].nunique()

valid_seva = seva[seva["Building"].astype(str).str.strip() != ""].copy()
assigned = len(valid_seva)
completed = int((valid_seva["Status"].astype(str).str.lower() == "completed").sum())
pending = max(assigned - completed, 0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Members", total_members)
c2.metric("Buildings", total_buildings)
c3.metric("Seva Entries", assigned)
c4.metric("Completed", completed)

tab1, tab2, tab3 = st.tabs(["📋 Seva Board", "➕ Add New Member", "👥 Members"])

# ---------------- Seva Board ----------------
with tab1:
    filtered = seva.copy()

    if selected_day != "All Days":
        day_name = selected_day.split(" — ")[0]
        filtered = filtered[filtered["Day"] == day_name]

    if selected_building != "All Buildings":
        filtered = filtered[filtered["Building"] == selected_building]

    if selected_status != "All":
        filtered = filtered[filtered["Status"] == selected_status]

    if selected_sevarthi.strip():
        q = selected_sevarthi.strip().lower()
        mask = (
            filtered["Sevarthi 1"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["Sevarthi 2"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["Sevarthi 3"].astype(str).str.lower().str.contains(q, na=False)
        )
        filtered = filtered[mask]

    if search.strip():
        q = search.strip().lower()
        mask = (
            filtered["Member / Household"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["Flat"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["Building"].astype(str).str.lower().str.contains(q, na=False)
        )
        filtered = filtered[mask]

    st.subheader("Seva Schedule")
    st.write(f"Showing **{len(filtered)}** entries")

    if filtered.empty:
        st.info("No Seva entries match the selected filters.")
    else:
        # Join contact details from Members
        contact_map = members.set_index(["Building", "Flat"])
        for _, row in filtered.sort_values(["Date", "Building", "Flat", "Time"]).iterrows():
            key = (row["Building"], row["Flat"])
            contact_row = contact_map.loc[key] if key in contact_map.index else None

            phone_html = ""
            address = ""
            if contact_row is not None and not isinstance(contact_row, pd.DataFrame):
                phones = [contact_row.get(c, "") for c in ["Contact 1", "Contact 2", "Contact 3"]]
                phones = [p for p in phones if str(p).strip()]
                phone_html = " · ".join(
                    [f'<a href="{tel_link(p)}">{p}</a>' for p in phones]
                )
                address = str(contact_row.get("Address", ""))

            date_index = next((i for i, x in enumerate(DAYS) if x[0] == row["Day"]), 0)
            bg = DAY_COLORS[date_index]

            st.markdown(
                f"""
                <div class="seva-card" style="background:{bg}">
                    <div style="font-size:1.15rem;font-weight:700">
                        {row["Day"]} · {row["Date"]} · {row["Time"] or "Time not set"}
                    </div>
                    <div style="font-size:1.1rem;margin-top:5px">
                        <b>{row["Member / Household"]}</b>
                    </div>
                    <div>{row["Building"]} · Flat {row["Flat"]}</div>
                    <div class="small">{address}</div>
                    <div style="margin-top:8px">📞 {phone_html or "No contact number"}</div>
                    <div style="margin-top:8px">
                        🙏 <b>Sevarthi 1:</b> {row["Sevarthi 1"] or "—"}
                        &nbsp;&nbsp; <b>Sevarthi 2:</b> {row["Sevarthi 2"] or "—"}
                        &nbsp;&nbsp; <b>Sevarthi 3:</b> {row["Sevarthi 3"] or "—"}
                    </div>
                    <div style="margin-top:6px"><b>Status:</b> {row["Status"] or "Planned"}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            b1, b2 = st.columns([1, 5])
            with b1:
                if address:
                    st.link_button("📍 Maps", maps_url(address), use_container_width=True)
            with b2:
                if row["Notes"]:
                    st.caption("Notes: " + str(row["Notes"]))

        st.download_button(
            "⬇️ Download filtered Seva list",
            filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name="seva_filtered.csv",
            mime="text/csv",
        )

# ---------------- Add New Member ----------------
with tab2:
    st.subheader("Add New Member + Select Seva Days")
    st.caption("Only fill the days on which this member should receive Seva planning. The app creates one Seva row for each selected day.")

    with st.form("new_member_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            building = st.text_input("Building *")
            flat = st.text_input("Flat / House No. *")
            name = st.text_input("Name *")
            age = st.number_input("Age", min_value=0, max_value=120, value=0, step=1)
        with col2:
            contact1 = st.text_input("Contact 1")
            contact2 = st.text_input("Contact 2")
            contact3 = st.text_input("Contact 3")
            default_status = st.selectbox("Initial Seva Status", ["Planned", "Confirmed"])
        with col3:
            address = st.text_area("Address *", height=125)
            selected_days = st.multiselect(
                "Select Seva Days *",
                [f"{d} — {pd.to_datetime(dt).strftime('%d %b %Y')}" for d, dt, _ in DAYS],
                default=[],
            )

        submitted = st.form_submit_button("➕ Add Member & Create Seva Entries", use_container_width=True)

    if submitted:
        if not building.strip() or not flat.strip() or not name.strip() or not address.strip():
            st.error("Please fill Building, Flat, Name and Address.")
        elif not selected_days:
            st.error("Select at least one Seva day.")
        else:
            building = standardize_building(building)
            member = {
                "Building": building,
                "Flat": flat.strip(),
                "Name": name.strip(),
                "Age": "" if age == 0 else str(age),
                "Address": address.strip(),
                "Contact 1": contact1.strip(),
                "Contact 2": contact2.strip(),
                "Contact 3": contact3.strip(),
            }

            append_member(members_ws, member)

            new_rows = []
            for item in selected_days:
                day_name = item.split(" — ")[0]
                day_date = next(dt for d, dt, _ in DAYS if d == day_name)
                new_rows.append([
                    day_date, day_name, "", building, flat.strip(), name.strip(),
                    "", "", "", default_status, ""
                ])

            append_seva_rows(seva_ws, new_rows)
            st.success(f"Added {name} and created {len(new_rows)} Seva entries.")
            refresh()

# ---------------- Members ----------------
with tab3:
    st.subheader("Members")
    display = members.copy()
    if selected_building != "All Buildings":
        display = display[display["Building"] == selected_building]
    if search.strip():
        q = search.strip().lower()
        display = display[
            display.astype(str).apply(
                lambda col: col.str.lower().str.contains(q, na=False)
            ).any(axis=1)
        ]
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download Members",
        display.to_csv(index=False).encode("utf-8-sig"),
        file_name="members.csv",
        mime="text/csv",
    )

st.divider()
st.caption("Seva Planner • Google Sheets is the master data source • Samet Shikhar and Samet Shikhar Mahal are standardized as Samet Shikhar Mahal")

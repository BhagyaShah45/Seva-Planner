import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
import html
import textwrap

# ============================================================
# SEVA PLANNER
# ============================================================

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
    "#E4DFEC", "#D9EAD3", "#D0E0E3", "#F4CCCC",
]

MEMBER_COLS = [
    "Building", "Flat", "Name", "Age", "Address",
    "Contact 1", "Contact 2", "Contact 3",
]

SEVA_COLS = [
    "Date", "Day", "Time", "Building", "Flat",
    "Member / Household", "Sevarthi 1", "Sevarthi 2",
    "Sevarthi 3", "Status", "Notes",
]

STATUS_OPTIONS = ["Planned", "Confirmed", "Completed", "Cancelled"]


# ============================================================
# HELPERS
# ============================================================

def txt(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def safe_html(value):
    return html.escape(txt(value))


def phone(value):
    return re.sub(r"[^0-9+]", "", txt(value))


def building(value):
    value = txt(value)
    if value.lower() in {"samet shikhar", "samet shikhar mahal"}:
        return "Samet Shikhar Mahal"
    return value


def day_label(day, date):
    return f"{day} — {pd.to_datetime(date).strftime('%d %b %Y')}"


def normalize(df, cols):
    df = pd.DataFrame() if df is None else df.copy()

    for col in cols:
        if col not in df.columns:
            df[col] = ""

    df = df[cols].fillna("")

    if "Building" in df.columns:
        df["Building"] = df["Building"].map(building)

    if "Flat" in df.columns:
        df["Flat"] = df["Flat"].map(txt)

    if "Name" in df.columns:
        df["Name"] = df["Name"].map(txt)

    if "Member / Household" in df.columns:
        df["Member / Household"] = df["Member / Household"].map(txt)

    if "Status" in df.columns:
        df["Status"] = df["Status"].map(txt)
        df.loc[df["Status"] == "", "Status"] = "Planned"

    if "Date" in df.columns:
        parsed = pd.to_datetime(df["Date"], errors="coerce")
        df["Date"] = parsed.dt.strftime("%Y-%m-%d").fillna("")

    # IMPORTANT:
    # Always derive Day 1-Day 8 from Date when the date belongs
    # to this Seva schedule. This fixes sheets where Day contains
    # weekday names such as Tuesday instead of Day 1.
    if "Day" in df.columns and "Date" in df.columns:
        date_to_day = {date: day for day, date in DAYS}
        derived_day = df["Date"].map(date_to_day)
        existing_day = df["Day"].map(txt)

        df["Day"] = derived_day.where(
            derived_day.notna(),
            existing_day,
        ).fillna("")

    return df


# ============================================================
# GOOGLE SHEETS
# ============================================================

@st.cache_resource
def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    if "gcp_service_account" not in st.secrets:
        raise KeyError(
            'Missing "gcp_service_account" in secrets.toml.'
        )

    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )

    return gspread.authorize(credentials)


def spreadsheet():
    client = get_client()

    if "google_sheet" in st.secrets:
        name = st.secrets["google_sheet"]["spreadsheet_name"]
    elif "google" in st.secrets:
        name = st.secrets["google"]["spreadsheet_name"]
    else:
        raise KeyError(
            "Missing [google_sheet] or [google] "
            "spreadsheet_name in secrets.toml."
        )

    return client.open(name)


def ws(sheet, name):
    try:
        return sheet.worksheet(name)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(
            title=name,
            rows=2000,
            cols=20,
        )


def ensure_headers(sheet, cols):
    existing = sheet.row_values(1)

    if existing != cols:
        if sheet.col_count < len(cols):
            sheet.add_cols(len(cols) - sheet.col_count)
        sheet.update("A1", [cols])


def fetch_data():
    sheet = spreadsheet()
    members_ws = ws(sheet, "Members")
    seva_ws = ws(sheet, "Seva")

    ensure_headers(members_ws, MEMBER_COLS)
    ensure_headers(seva_ws, SEVA_COLS)

    members = normalize(
        pd.DataFrame(members_ws.get_all_records()),
        MEMBER_COLS,
    )

    seva = normalize(
        pd.DataFrame(seva_ws.get_all_records()),
        SEVA_COLS,
    )

    return members, seva


def save_member(member):
    sheet = ws(spreadsheet(), "Members")
    ensure_headers(sheet, MEMBER_COLS)

    sheet.append_row(
        [member.get(col, "") for col in MEMBER_COLS],
        value_input_option="USER_ENTERED",
    )


def save_seva(rows):
    if not rows:
        return

    sheet = ws(spreadsheet(), "Seva")
    ensure_headers(sheet, SEVA_COLS)

    sheet.append_rows(
        rows,
        value_input_option="USER_ENTERED",
    )


# ============================================================
# SESSION-STATE DATA
# Google Sheet is NOT fetched when filters change.
# ============================================================

def load_once():
    if (
        "members_data" not in st.session_state
        or "seva_data" not in st.session_state
    ):
        with st.spinner("Loading Google Sheet data..."):
            members, seva = fetch_data()

        st.session_state.members_data = members
        st.session_state.seva_data = seva
        st.session_state.loaded_at = pd.Timestamp.now()


def refresh():
    with st.spinner("Refreshing Google Sheet data..."):
        members, seva = fetch_data()

    st.session_state.members_data = members
    st.session_state.seva_data = seva
    st.session_state.loaded_at = pd.Timestamp.now()


# ============================================================
# MOBILE-FRIENDLY CSS
# ============================================================

st.markdown(
    textwrap.dedent("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    .hero {
        padding: 22px 26px;
        border-radius: 20px;
        background: linear-gradient(135deg, #f7f8fc, #eef3f8);
        border: 1px solid #e1e6ed;
        margin-bottom: 18px;
    }

    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.15;
    }

    .hero-subtitle {
        color: #667085;
        margin-top: 7px;
        font-size: .95rem;
    }

    .seva-card {
        border-radius: 16px;
        padding: 17px;
        margin-bottom: 12px;
        border: 1px solid rgba(0,0,0,.10);
        box-shadow: 0 2px 8px rgba(0,0,0,.04);
        overflow-wrap: anywhere;
    }

    .small {
        font-size: .88rem;
        color: #667085;
        margin-top: 6px;
        line-height: 1.45;
    }

    .pill {
        display: inline-block;
        padding: 5px 9px;
        border-radius: 999px;
        background: rgba(255,255,255,.78);
        border: 1px solid rgba(0,0,0,.08);
        font-size: .82rem;
        font-weight: 700;
        margin: 4px 4px 0 0;
    }

    .filter-note {
        color: #667085;
        font-size: .88rem;
        margin-bottom: 8px;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.55rem;
    }

    /* Keep tables usable on narrow screens */
    [data-testid="stDataFrame"] {
        width: 100%;
    }

    /* Mobile */
    @media (max-width: 768px) {
        .block-container {
            padding: .65rem .75rem 1.5rem .75rem;
        }

        .hero {
            padding: 17px;
            border-radius: 15px;
        }

        .hero-title {
            font-size: 1.55rem;
        }

        .hero-subtitle {
            font-size: .82rem;
        }

        .seva-card {
            padding: 14px;
            border-radius: 14px;
        }

        .small {
            font-size: .82rem;
        }

        .pill {
            display: block;
            width: 100%;
            box-sizing: border-box;
            margin-right: 0;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.2rem;
        }

        [data-testid="stMetricLabel"] {
            font-size: .75rem;
        }

        /* Stack Streamlit columns naturally for filters */
        [data-testid="stHorizontalBlock"] {
            gap: .45rem;
        }

        /* Make buttons easy to tap */
        .stButton > button,
        .stDownloadButton > button,
        .stFormSubmitButton > button {
            min-height: 44px;
        }

        input, textarea, select {
            font-size: 16px !important;
        }

        /* Prevent wide dataframe from breaking page */
        [data-testid="stDataFrame"] > div {
            max-width: 100%;
            overflow-x: auto;
        }
    }
    </style>
    """).strip(),
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">🙏 Seva Planner</div>
        <div class="hero-subtitle">
            Home Seva management • Google Sheets master data •
            Smart filters • Sevarthi assignment
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# INITIAL LOAD
# ============================================================

try:
    load_once()
except Exception as exc:
    st.error("Google Sheets connection could not be loaded.")
    st.code(str(exc))
    st.info(
        "Check .streamlit/secrets.toml and make sure the "
        "Google Sheet is shared with the service-account email."
    )
    st.stop()


members = st.session_state.members_data.copy()
seva = st.session_state.seva_data.copy()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("➕ Add New Member")
    st.caption(
        "Add a member and create Seva entries only for "
        "the selected days."
    )

    with st.form("new_member_form", clear_on_submit=True):
        nb = st.text_input("Building *")
        nf = st.text_input("Flat / House No. *")
        nn = st.text_input("Name *")
        na = st.number_input("Age", 0, 120, 0, 1)
        naddr = st.text_area("Address *", height=90)

        st.markdown("**Contact Numbers**")
        nc1 = st.text_input("Contact 1")
        nc2 = st.text_input("Contact 2")
        nc3 = st.text_input("Contact 3")

        ns = st.selectbox(
            "Initial Seva Status",
            STATUS_OPTIONS[:2],
        )

        nd = st.multiselect(
            "Select Seva Days *",
            [day_label(d, dt) for d, dt in DAYS],
        )

        submitted = st.form_submit_button(
            "➕ Add Member & Create Seva",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        nb = building(nb)
        nf = nf.strip()
        nn = nn.strip()
        naddr = naddr.strip()

        if not nb or not nf or not nn or not naddr:
            st.error(
                "Please fill Building, Flat, Name and Address."
            )
        elif not nd:
            st.error("Select at least one Seva day.")
        else:
            dup = members[
                (
                    members["Building"]
                    .astype(str)
                    .str.lower()
                    .str.strip()
                    == nb.lower()
                )
                &
                (
                    members["Flat"]
                    .astype(str)
                    .str.lower()
                    .str.strip()
                    == nf.lower()
                )
                &
                (
                    members["Name"]
                    .astype(str)
                    .str.lower()
                    .str.strip()
                    == nn.lower()
                )
            ]

            if not dup.empty:
                st.error(
                    "This member already exists for the same "
                    "building and flat."
                )
            else:
                member = {
                    "Building": nb,
                    "Flat": nf,
                    "Name": nn,
                    "Age": "" if na == 0 else int(na),
                    "Address": naddr,
                    "Contact 1": nc1.strip(),
                    "Contact 2": nc2.strip(),
                    "Contact 3": nc3.strip(),
                }

                rows = []

                for item in nd:
                    day_name = item.split(" — ", 1)[0]

                    day_date = next(
                        dt for d, dt in DAYS if d == day_name
                    )

                    rows.append([
                        day_date,
                        day_name,
                        "",
                        nb,
                        nf,
                        nn,
                        "",
                        "",
                        "",
                        ns,
                        "",
                    ])

                try:
                    save_member(member)
                    save_seva(rows)

                    st.session_state.members_data = pd.concat(
                        [
                            members,
                            pd.DataFrame(
                                [member],
                                columns=MEMBER_COLS,
                            ),
                        ],
                        ignore_index=True,
                    )

                    st.session_state.seva_data = pd.concat(
                        [
                            seva,
                            pd.DataFrame(
                                rows,
                                columns=SEVA_COLS,
                            ),
                        ],
                        ignore_index=True,
                    )

                    st.success(
                        f"Added {nn} and created {len(rows)} "
                        "Seva entries."
                    )
                    st.rerun()

                except Exception as exc:
                    st.error("Could not save the new member.")
                    st.code(str(exc))

    st.divider()
    st.subheader("☁️ Google Sheets")
    st.caption(
        "Google Sheet data is fetched only on initial load "
        "or manual refresh."
    )

    if st.button(
        "🔄 Refresh Google Sheet Data",
        use_container_width=True,
    ):
        try:
            refresh()
            st.rerun()
        except Exception as exc:
            st.error("Refresh failed.")
            st.code(str(exc))

    if "loaded_at" in st.session_state:
        st.caption(
            "Loaded: "
            + pd.to_datetime(
                st.session_state.loaded_at
            ).strftime("%d %b %Y, %I:%M %p")
        )


# ============================================================
# FILTER OPTIONS
# ============================================================

st.subheader("🎯 Seva Filters")
st.markdown(
    '<div class="filter-note">'
    'Filters use the data currently loaded in the app. '
    'They do not fetch Google Sheets again.'
    '</div>',
    unsafe_allow_html=True,
)

names = sorted(
    [txt(x) for x in members["Name"].unique() if txt(x)],
    key=str.casefold,
)

buildings = sorted(
    [txt(x) for x in members["Building"].unique() if txt(x)],
    key=str.casefold,
)

sevarthis = set()

for col in ["Sevarthi 1", "Sevarthi 2", "Sevarthi 3"]:
    sevarthis.update(
        x for x in seva[col].map(txt).unique() if x
    )

statuses = sorted(
    [txt(x) for x in seva["Status"].unique() if txt(x)],
    key=str.casefold,
)


# ============================================================
# MAIN FILTERS
#
# Row 1: Day / Building / Member
# Row 2: Sevarthi / Status / Quick Search
#
# NO FLAT FILTER
# ============================================================

f1, f2, f3 = st.columns(3)

with f1:
    selected_day = st.selectbox(
        "📅 Seva Day",
        ["All Days"] + [
            day_label(d, dt) for d, dt in DAYS
        ],
    )

with f2:
    selected_building = st.selectbox(
        "🏢 Building",
        ["All Buildings"] + buildings,
    )

with f3:
    selected_member = st.selectbox(
        "👤 Member",
        ["All Members"] + names,
    )


f4, f5, f6 = st.columns([1, 1, 2])

with f4:
    selected_sevarthi = st.selectbox(
        "🙏 Sevarthi",
        ["All Sevarthi"] + sorted(
            sevarthis,
            key=str.casefold,
        ),
    )

with f5:
    selected_status = st.selectbox(
        "📌 Status",
        ["All Status"] + statuses,
    )

with f6:
    quick_search = st.text_input(
        "🔎 Quick Search",
        placeholder="Search name, building, flat or address...",
    )


# ============================================================
# FILTER DATA
# ============================================================

filtered = seva.copy()

# Day filter
if selected_day != "All Days":
    wanted_day = (
        selected_day
        .split(" — ", 1)[0]
        .strip()
        .casefold()
    )

    day_series = (
        filtered["Day"]
        .astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
        .str.casefold()
    )

    filtered = filtered[day_series == wanted_day]

# Building filter
if selected_building != "All Buildings":
    filtered = filtered[
        filtered["Building"]
        .astype(str)
        .str.strip()
        .str.casefold()
        == selected_building.casefold()
    ]

# Member filter
if selected_member != "All Members":
    filtered = filtered[
        filtered["Member / Household"]
        .astype(str)
        .str.contains(
            re.escape(selected_member),
            case=False,
            na=False,
        )
    ]

# Sevarthi filter
if selected_sevarthi != "All Sevarthi":
    mask = pd.Series(False, index=filtered.index)

    for col in ["Sevarthi 1", "Sevarthi 2", "Sevarthi 3"]:
        mask |= filtered[col].astype(str).str.contains(
            re.escape(selected_sevarthi),
            case=False,
            na=False,
        )

    filtered = filtered[mask]

# Status filter
if selected_status != "All Status":
    filtered = filtered[
        filtered["Status"]
        .astype(str)
        .str.strip()
        .str.casefold()
        == selected_status.casefold()
    ]

# Quick search
if quick_search.strip():
    q = re.escape(quick_search.strip())

    # Add household address into the searchable fields.
    address_lookup = {}

    for _, member_row in members.iterrows():
        key = (
            txt(member_row["Building"]).casefold(),
            txt(member_row["Flat"]).casefold(),
        )

        address_lookup.setdefault(key, [])

        address = txt(member_row["Address"])

        if address and address not in address_lookup[key]:
            address_lookup[key].append(address)

    search_mask = pd.Series(
        False,
        index=filtered.index,
    )

    for idx, row in filtered.iterrows():
        values = [
            txt(row["Member / Household"]),
            txt(row["Building"]),
            txt(row["Flat"]),
            txt(row["Sevarthi 1"]),
            txt(row["Sevarthi 2"]),
            txt(row["Sevarthi 3"]),
            txt(row["Status"]),
            txt(row["Notes"]),
        ]

        key = (
            txt(row["Building"]).casefold(),
            txt(row["Flat"]).casefold(),
        )

        values.extend(address_lookup.get(key, []))

        search_mask.loc[idx] = any(
            re.search(q, value, flags=re.IGNORECASE)
            for value in values
        )

    filtered = filtered[search_mask]


# ============================================================
# DASHBOARD
# ============================================================

#st.divider()
#st.subheader("📊 Dashboard")

#valid = seva[
#    seva["Building"]
#    .astype(str)
 #   .str.strip()
 #   != ""
#]

#k = st.columns(2)

#k[0].metric(
   # "Members",
   # int(
     #   (
        #    members["Name"]
          #  .astype(str)
      #      .str.strip()
         #   != ""
      #  ).sum()
   # ),
#)

#k[1].metric(
 #   "Buildings",
   # int(
 #       members["Building"]
    #    .astype(str)
    #    .str.strip()
    #    .replace("", pd.NA)
     #   .nunique()
   # ),
#)

# k[2].metric(
#     "Seva Entries",
#     len(valid),
# )

# k[3].metric(
#     "Completed",
#     int(
#         valid["Status"]
#         .astype(str)
#         .str.lower()
#         .eq("completed")
#         .sum()
#     ),
# )

# k[4].metric(
#     "Confirmed",
#     int(
#         valid["Status"]
#         .astype(str)
#         .str.lower()
#         .eq("confirmed")
#         .sum()
#     ),
# )

# k[5].metric(
#     "Planned",
#     int(
#         valid["Status"]
#         .astype(str)
#         .str.lower()
#         .eq("planned")
#         .sum()
#     ),
# )


# ============================================================
# SEVA BOARD
# ============================================================

st.divider()
st.subheader(
    f"🙏 Seva Board • {len(filtered)} entries"
)

if filtered.empty:
    st.info(
        "No Seva entries match the selected filters."
    )

else:
    filtered = filtered.copy()

    filtered["_sort"] = pd.to_datetime(
        filtered["Date"],
        errors="coerce",
    )

    filtered = filtered.sort_values(
        ["_sort", "Building", "Flat", "Time"],
        na_position="last",
    )

    for _, row in filtered.iterrows():

        b = txt(row["Building"])
        flat = txt(row["Flat"])

        # Match all members in the same building + flat,
        # so multiple members in one flat are handled safely.
        household = members[
            (
                members["Building"]
                .astype(str)
                .str.strip()
                .str.casefold()
                == b.casefold()
            )
            &
            (
                members["Flat"]
                .astype(str)
                .str.strip()
                .str.casefold()
                == flat.casefold()
            )
        ]

        phones = []
        addresses = []

        for _, member_row in household.iterrows():

            for contact_col in [
                "Contact 1",
                "Contact 2",
                "Contact 3",
            ]:
                p = txt(member_row[contact_col])

                if p and p not in phones:
                    phones.append(p)

            address = txt(member_row["Address"])

            if address and address not in addresses:
                addresses.append(address)

        address_text = " / ".join(addresses)

        phone_html = " · ".join(
            [
                (
                    f'<a href="tel:{phone(p)}">'
                    f"{safe_html(p)}</a>"
                )
                for p in phones
            ]
        )

        parsed_date = pd.to_datetime(
            row["Date"],
            errors="coerce",
        )

        date_text = (
            ""
            if pd.isna(parsed_date)
            else parsed_date.strftime("%d %b %Y")
        )

        day_name = txt(row["Day"])

        status = txt(row["Status"]) or "Planned"

        status_icon = {
            "completed": "✅",
            "confirmed": "🟢",
            "cancelled": "❌",
        }.get(
            status.casefold(),
            "🟡",
        )

        day_index = next(
            (
                i
                for i, (d, _) in enumerate(DAYS)
                if d.casefold() == day_name.casefold()
            ),
            0,
        )

        bg = DAY_COLORS[
            day_index % len(DAY_COLORS)
        ]

        card = textwrap.dedent(f"""
        <div class="seva-card"
             style="background:{bg}">

            <div>
                <b>
                    {safe_html(day_name)}
                    ·
                    {safe_html(date_text)}
                    ·
                    {safe_html(txt(row["Time"]) or "Time not set")}
                </b>
            </div>

            <div style="
                font-size:1.15rem;
                font-weight:800;
                margin-top:6px;
            ">
                {safe_html(row["Member / Household"])}
            </div>

            <div style="margin-top:4px">
                🏢 <b>{safe_html(b)}</b>
                · Flat <b>{safe_html(flat)}</b>
            </div>

            <div class="small">
                📍 {safe_html(address_text or "Address not available")}
            </div>

            <div class="small">
                📞 {phone_html or "No contact number"}
            </div>

            <div style="margin-top:9px">
                <span class="pill">
                    🙏 Sevarthi 1:
                    {safe_html(txt(row["Sevarthi 1"]) or "—")}
                </span>

                <span class="pill">
                    🙏 Sevarthi 2:
                    {safe_html(txt(row["Sevarthi 2"]) or "—")}
                </span>

                <span class="pill">
                    🙏 Sevarthi 3:
                    {safe_html(txt(row["Sevarthi 3"]) or "—")}
                </span>
            </div>

            <div style="margin-top:9px">
                {status_icon}
                <b>Status:</b> {safe_html(status)}
            </div>

        </div>
        """).strip()

        # Render as native HTML, NOT Markdown.
        # This prevents indented HTML from appearing as a code block.
        st.html(card)

        notes = txt(row["Notes"])

        if notes:
            st.caption("📝 " + notes)

    st.download_button(
        "⬇️ Download Filtered Seva CSV",
        filtered
        .drop(columns=["_sort"], errors="ignore")
        .to_csv(index=False)
        .encode("utf-8-sig"),
        "seva_filtered.csv",
        "text/csv",
        use_container_width=True,
    )


# ============================================================
# MEMBERS
# ============================================================

st.divider()
st.subheader("👥 Members")

member_display = members.copy()

if selected_building != "All Buildings":
    member_display = member_display[
        member_display["Building"]
        .astype(str)
        .str.strip()
        .str.casefold()
        == selected_building.casefold()
    ]

if selected_member != "All Members":
    member_display = member_display[
        member_display["Name"]
        .astype(str)
        .str.strip()
        .str.casefold()
        == selected_member.casefold()
    ]

if quick_search.strip():
    q = re.escape(quick_search.strip())

    member_display = member_display[
        member_display.astype(str)
        .apply(
            lambda col: col.str.contains(
                q,
                case=False,
                na=False,
            )
        )
        .any(axis=1)
    ]

st.dataframe(
    member_display,
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "⬇️ Download Members CSV",
    member_display
    .to_csv(index=False)
    .encode("utf-8-sig"),
    "members.csv",
    "text/csv",
    use_container_width=True,
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Seva Planner • Google Sheets is the master data source • "
    "Data is fetched only on initial load and manual refresh."
)

# Seva Planner — Streamlit + Google Sheets

A complete home-Seva management app. Google Sheets is the master data source.

## Features
- Dashboard with members, buildings, Seva entries and completed count
- Seva Board with filters for day, building, Sevarthi, member/flat and status
- Contact numbers with clickable phone links
- Google Maps button for addresses
- Day-specific colors for all 8 days
- Add a new member and select exactly which Seva days are needed
- Automatically creates Seva rows for selected days
- Download filtered Seva list as CSV
- Standardizes "Samet Shikhar" and "Samet Shikhar Mahal" to "Samet Shikhar Mahal"

## Google Sheet structure

Create a Google Spreadsheet and name it exactly as configured in `.streamlit/secrets.toml`.

Create these two worksheets:

### Members
Columns:
Building | Flat | Name | Age | Address | Contact 1 | Contact 2 | Contact 3

### Seva
Columns:
Date | Day | Time | Building | Flat | Member / Household | Sevarthi 1 | Sevarthi 2 | Sevarthi 3 | Status | Notes

The app will create missing worksheets/headers automatically.

## Google service account

1. Create a Google Cloud service account.
2. Enable Google Sheets API and Google Drive API.
3. Download the service-account JSON.
4. Share your Google Spreadsheet with the service-account email as Editor.
5. Put the credentials into Streamlit secrets.

### Streamlit Cloud secrets example

Create `.streamlit/secrets.toml`:

```toml
[google_sheet]
spreadsheet_name = "YOUR GOOGLE SHEET NAME"

[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "YOUR_SERVICE_ACCOUNT_EMAIL"
client_id = "YOUR_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "YOUR_CLIENT_CERT_URL"
universe_domain = "googleapis.com"
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important
Do not commit the `.streamlit/secrets.toml` file to GitHub.

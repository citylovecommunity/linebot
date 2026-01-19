# etl_pipeline.py
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert

from shared.database.session_maker import get_session_factory
from shared.database.models import Member
# Assumes you saved the UserProfileAdapter class from our previous conversation in logic.py
from shared.scoring import UserProfileAdapter

load_dotenv()

# --- Config ---
TZ = ZoneInfo('Asia/Taipei')
DB_URL = os.getenv("DB")
SHEET_NAME = "(後台綁定)城遇訪談表單 (回覆)"

# --- Setup Connection ---
SessionLocal = get_session_factory(DB_URL)


def parse_chinese_datetime(text):
    """Parses '2025/12/9 上午 11:25:56' into datetime object"""
    try:
        if not text:
            return None
        date_part, meridiem, time_part = text.split()
        hour, minute, second = map(int, time_part.split(':'))

        if meridiem == '下午' and hour < 12:
            hour += 12
        elif meridiem == '上午' and hour == 12:
            hour = 0

        dt_str = f"{date_part} {hour:02}:{minute:02}:{second:02}"
        # Make it timezone aware immediately
        dt_naive = datetime.strptime(dt_str, "%Y/%m/%d %H:%M:%S")
        return dt_naive.replace(tzinfo=TZ)
    except Exception as e:
        print(f"Date Parse Error for {text}: {e}")
        return None


def fetch_google_sheet_data():
    print("Fetching data from Google Sheets...")
    gc = gspread.service_account('service_account.json')
    wks = gc.open(SHEET_NAME).sheet1

    # Get all records as a list of dicts (easier for ORM than DataFrame)
    return wks.get_all_records(numericise_ignore=["all"])


def transform_data(raw_records):
    """
    Converts raw Google Sheet dicts into a list of clean dictionaries 
    ready for the Member table.
    """
    clean_data_list = []

    for row in raw_records:
        # 1. Use our Adapter to handle the dirty JSON extraction logic
        adapter = UserProfileAdapter(row)

        # 2. Basic Parsing
        phone = str(row.get('您的連絡電話', '')).strip()
        if not phone:
            continue  # Skip invalid rows

        # 3. Create the clean dictionary map
        # This maps exactly to your DB columns
        member_dict = {
            # Identity
            "phone_number": phone,
            "name": row.get('您的全名'),
            "gender": row.get('您的性別', '')[0] if row.get('您的性別') else None,
            "email": row.get('您的通訊郵件'),
            "id_card_no": row.get('您的身分證字號'),

            # Status Flags
            # Logic from your pandas map
            "is_active": row.get('會員暫停') == "FALSE",
            "is_test": "測試" in str(row.get('這個帳號是誰？', '')),
            "fill_form_at": parse_chinese_datetime(row.get('時間戳記')),

            # --- THE NEW INSCRIBED COLUMNS (Extracted via Adapter) ---
            "birth_year": adapter.birth_year,
            "height": adapter.height,
            "rank": row.get("排約等級一", "B"),
            "marital_status": row.get("您目前的感情狀況", "Single"),
            "location_city": row.get("您的居住地", ""),

            # Preferences
            "pref_min_height": adapter.pref_min_height,
            "pref_max_height": adapter.pref_max_height,
            "pref_oldest_birth_year": adapter.pref_oldest_birth_year,
            "pref_youngest_birth_year": adapter.pref_youngest_birth_year,

            # The Payload
            "user_info": row
        }
        clean_data_list.append(member_dict)

    return clean_data_list


def load_data_bulk(clean_data):
    """
    Performs a Bulk Upsert using Postgres ON CONFLICT logic.
    """
    if not clean_data:
        print("No data to load.")
        return

    session = SessionLocal()
    try:
        # 1. Prepare the Insert Statement
        stmt = insert(Member).values(clean_data)

        # 2. Define the Upsert Logic (ON CONFLICT DO UPDATE)
        # We want to update everything EXCEPT 'id' and maybe 'created_at'
        update_dict = {
            col.name: col
            for col in stmt.excluded
            if col.name != 'id'  # Protect ID
        }

        # 3. Execute
        final_stmt = stmt.on_conflict_do_update(
            index_elements=['phone_number'],  # The unique constraint key
            set_=update_dict
        )

        result = session.execute(final_stmt)
        session.commit()
        print(f"Success: Processed {len(clean_data)} rows.")

    except Exception as e:
        session.rollback()
        print(f"Error during bulk load: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    # 1. Extract
    raw_data = fetch_google_sheet_data()

    # 2. Transform (Clean & Extract Grading Attributes)
    clean_data = transform_data(raw_data)

    # 3. Load (Upsert)
    load_data_bulk(clean_data)

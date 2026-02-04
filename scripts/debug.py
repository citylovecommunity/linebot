from form_app.extensions import line_bot_helper
from form_app.services.messaging import process_all_notifications, collect_unread_message_texts, collect_date_proposal_texts
from config import SessionFactory
from dotenv import load_dotenv
import os
from shared.database.models import Message

load_dotenv()

with SessionFactory() as session:
    # print(process_all_notifications(session, dev=True,
    #       test_user_id=os.getenv('TEST_USER_ID')))
    print(collect_date_proposal_texts(session))

from form_app.database import get_db

from form_app.services.messaging import process_all_notifications, collect_unread_message_texts, collect_date_proposal_texts


with get_db() as session:
    # print(process_all_notifications(session, dev=True,
    #       test_user_id=os.getenv('TEST_USER_ID')))
    print(collect_unread_message_texts(session))

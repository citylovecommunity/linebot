from flask import Blueprint, current_app, request

from form_app.config import settings
from form_app.database import get_db

bp = Blueprint('tasks_bp', __name__, url_prefix='/tasks')


@bp.route('/send-notifications', methods=['POST'])
def task_send_notifications():
    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    from form_app.services.messaging import process_all_notifications

    # Pass the session to the new processor
    session = get_db()
    process_all_notifications(session)

    session.commit()
    current_app.logger.info("已傳送line通知！！")

    return "OK", 200


@bp.route('/match-all-users', methods=['POST'])
def task_match_all_users():
    """
    Match all Users, also do the scoring
    """

    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    from form_app.services.matching import process_matches_bulk
    from form_app.services.scoring import (get_eligible_matching_pool,
                                           run_matching_score_optimized)

    session = get_db()
    eligible_members = get_eligible_matching_pool(session)
    run_matching_score_optimized(eligible_members, session)
    process_matches_bulk(eligible_members, session)
    session.commit()
    current_app.logger.info("已批量配對用戶")

    return "OK", 200


@bp.route('/load-data-from-gs', methods=['POST'])
def task_load_data_from_gs():
    """
    Match all Users, also do the scoring
    """

    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    from form_app.services.load_user import (fetch_google_sheet_data,
                                             load_data_bulk, transform_data)

    session = get_db()
    raw_data = fetch_google_sheet_data()

    clean_data = transform_data(raw_data)
    load_data_bulk(clean_data, session)

    session.commit()
    current_app.logger.info("已將google sheet資料搬運至資料庫")

    return "OK", 200

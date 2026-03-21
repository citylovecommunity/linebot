from datetime import date

from flask import Blueprint, current_app, request

from form_app.config import settings
from form_app.database import get_db

bp = Blueprint('tasks_bp', __name__, url_prefix='/tasks')


@bp.route('/send-notifications', methods=['POST'])
def task_send_notifications():
    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    from form_app.services.messaging import process_all_notifications

    session = get_db()
    process_all_notifications(session)
    session.commit()
    current_app.logger.info("已傳送line通知！！")

    return "OK", 200


@bp.route('/match-all-users', methods=['POST'])
def task_match_all_users():
    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    # ?skip_notify=true: insert matchings but skip LINE notifications.
    # Use this when users have already been notified but the previous run's
    # commit failed and the matchings were never persisted.
    skip_notify = request.args.get('skip_notify', 'false').lower() == 'true'

    from form_app.models import Matching
    from form_app.services.matching import process_matches_bulk
    from form_app.services.messaging import process_all_notifications
    from form_app.services.scoring import get_eligible_matching_pool, run_matching_score_optimized

    session = get_db()
    eligible_members = get_eligible_matching_pool(session)
    run_matching_score_optimized(eligible_members, session)
    process_matches_bulk(eligible_members, session)

    if skip_notify:
        # Mark every unnotified matching (including the ones just created) as
        # already notified so the next send-notifications run won't fire them.
        new_matchings = session.query(Matching).filter(
            Matching.is_match_notified.is_not(True)
        ).all()
        for m in new_matchings:
            m.is_match_notified = True
        session.commit()
        current_app.logger.info(
            f"已批量配對用戶（skip_notify=true，共標記 {len(new_matchings)} 筆為已通知）"
        )
    else:
        # Commit matchings first so they exist even if the notification step fails.
        # LINE push_message is irreversible — it must happen only after the DB is safe.
        session.commit()
        process_all_notifications(session)
        session.commit()
        current_app.logger.info("已批量配對用戶並發送通知")

    return "OK", 200


@bp.route('/load-data-from-gs', methods=['POST'])
def task_load_data_from_gs():
    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    from form_app.services.load_user import fetch_google_sheet_data, load_data_bulk, transform_data

    session = get_db()
    raw_data = fetch_google_sheet_data()
    clean_data = transform_data(raw_data)
    load_data_bulk(clean_data, session)
    session.commit()
    current_app.logger.info("已將google sheet資料搬運至資料庫")

    return "OK", 200


@bp.route('/notify-expiring-members', methods=['POST'])
def task_notify_expiring_members():
    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    from dateutil.relativedelta import relativedelta
    from linebot import LineBotApi
    from linebot.models import TextSendMessage
    from sqlalchemy import and_

    from form_app.extensions import line_bot_helper
    from form_app.models import Member

    days_notice = int(request.args.get('days', 7))
    today = date.today()
    cutoff = today + relativedelta(days=days_notice)

    session = get_db()
    expiring = session.query(Member).filter(
        and_(
            Member.is_active == True,
            Member.is_test == False,
            Member.expiration_date != None,
            Member.expiration_date >= today,
            Member.expiration_date <= cutoff,
        )
    ).all()

    if not expiring:
        current_app.logger.info("notify-expiring-members: no expiring members found.")
        return "OK", 200

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)
    dev = settings.is_dev
    sent = 0

    for member in expiring:
        days_left = (member.expiration_date - today).days
        text = (
            f"親愛的 {member.proper_name}，\n\n"
            f"您的 CityLove 會員資格將於 {member.expiration_date.strftime('%Y/%m/%d')} 到期"
            f"（還有 {days_left} 天）。\n\n"
            f"如需續約，請聯絡我們的客服，謝謝！"
        )
        target = settings.LINE_TEST_USER_ID if dev else (
            member.line_info.user_id if member.line_info else None
        )
        if not target:
            current_app.logger.warning(
                f"notify-expiring-members: no LINE id for member {member.id}"
            )
            continue
        line_bot_api.push_message(target, TextSendMessage(text=text))
        sent += 1

    current_app.logger.info(f"notify-expiring-members: sent to {sent}/{len(expiring)} members.")
    return "OK", 200

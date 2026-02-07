from flask import Blueprint, current_app, request

from form_app.database import get_db
from form_app.services.messaging import process_all_notifications
from form_app.config import settings

bp = Blueprint('tasks_bp', __name__)


@bp.route('/tasks/send-notifications', methods=['POST'])
def task_send_notifications():
    if request.headers.get('X-Task-Secret') != settings.TASK_SECRET:
        return "Unauthorized", 401

    # Pass the session to the new processor
    process_all_notifications(get_db(), dev=settings.is_dev,
                              test_user_id=settings.LINE_TEST_USER_ID)

    current_app.logger.info("已傳送line通知！！")

    return "OK", 200

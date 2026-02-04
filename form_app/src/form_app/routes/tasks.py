from flask import Blueprint, current_app, request

from form_app.database import get_db
from form_app.services.messaging import process_all_notifications

bp = Blueprint('tasks_bp', __name__)


@bp.route('/tasks/send-notifications', methods=['POST'])
def task_send_notifications():
    if request.headers.get('X-Task-Secret') != current_app.config.get('TASK_SECRET'):
        return "Unauthorized", 401

    # Pass the session to the new processor
    process_all_notifications(get_db(), dev=current_app.config.get(
        "FLASK_DEBUG"), test_user_id=current_app.config.get("LINE_TEST_USER_ID"))

    return "OK", 200

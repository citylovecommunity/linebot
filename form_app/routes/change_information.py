from flask import render_template, request, url_for, Blueprint
from services.matching_services import get_matching_info_from_token, get_proper_name, change_state


from shared.database.models import Matching

change_information_bp = Blueprint('change_information_bp', __name__)


@app.route('/<token>/change_time/<who>/0818', methods=['GET', 'POST'])
def sudden_change_time(token, who):
    matching_info = get_token_matching(token)
    if who == 'sub':
        member_id = matching_info['subject_id']
        other_id = matching_info['object_id']
    elif who == 'obj':
        member_id = matching_info['object_id']
        other_id = matching_info['subject_id']
    else:
        return render_template('error.html', message='錯誤❌')

    if request.method == 'POST':
        message = request.form['message']

        # insert change_time_message
        change_time_stmt = """
        insert into sudden_change_time_history
        (member_id, created_at, matching_id, change_time_message)
        values (%s, now(), %s, %s)
        """

        conn = get_db()
        with conn.cursor() as curr:
            curr.execute(change_time_stmt, (member_id,
                                            matching_info['id'],
                                            message))

        change_state('dating_feedback_sending',
                     'change_time_notification_sending',
                     matching_info['id'])

        return render_template('thank_you.html',
                               header='已成功改期',
                               message=f"""
                               {get_proper_name(member_id)}已新增一筆超臨時改期紀錄<br>
                               此配對延後至下個月<br>
                               記得跟對方{get_proper_name(other_id)}講臨時取消！
                               """)
    else:
        return render_template(
            'change_time.html',
            header="超臨時改期！",
            message=f"是否對{get_proper_name(member_id)}觸發超臨時改期？",
            action_url=url_for('sudden_change_time', token=token, who=who))


@app.route('/<token>/change_time/<who>', methods=['GET', 'POST'])
def change_time(token, who):
    if request.method == 'POST':
        message = request.form['message']
        matching_info = get_token_matching(token)

        if who == 'sub':
            member_id = matching_info['subject_id']
        elif who == 'obj':
            member_id = matching_info['object_id']
        else:
            return render_template('error.html', message='錯誤❌')

        if matching_info['current_state'] not in ('deal_1d_notification_sending', 'deal_3d_notification_sending'):
            return render_template('error.html', message='目前狀態無法改期❌，請聯絡客服做處理！')

        # insert change_time_message
        change_time_stmt = """
        insert into change_time_history
        (member_id, created_at, matching_id, change_time_message)
        values (%s, now(), %s, %s)
        """

        conn = get_db()
        with conn.cursor() as curr:
            curr.execute(change_time_stmt, (member_id,
                                            matching_info['id'], message))

        change_state(('deal_1d_notification_sending', 'deal_3hr_notification_sending'),
                     'change_time_notification_sending',
                     matching_info['id'])

        return render_template('thank_you.html',
                               header='您已成功改期',
                               message="""
                               本配對已成功改期<br>
                               我們將重新為您安排配對<br>
                               請耐心等待後續通知<br>
                               """)
    else:
        return render_template('change_time.html',
                               header="臨時改期",
                               message="""
                                若您因臨時有事要取消本次約會<br>
                                請向對方說明您的理由<br>
                                我們將為您轉達給對方
                            """,
                               action_url=url_for('change_time', token=token, who=who))

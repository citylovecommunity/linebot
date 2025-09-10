
import os

import psycopg
from dotenv import load_dotenv
from flask import (Flask, g, redirect, render_template, request, session,
                   url_for)
from psycopg.rows import dict_row

app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True

load_dotenv()
app.secret_key = os.getenv('secret_key')
DB = os.getenv('DB')
ALLOW_CHANGE_STATE = os.getenv('ALLOW_CHANGE_STATE')
ALLOW_CHANGE_VALUE = os.getenv('ALLOW_CHANGE_VALUE')


def get_db():
    if 'db' not in g:
        g.db = psycopg.connect(DB)
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def get_token_matching(token):
    conn = get_db()
    with conn.cursor(row_factory=dict_row) as curr:
        stmt = "select id, subject_id, object_id, current_state from matching where access_token = %s;"
        result = curr.execute(stmt, (token,)).fetchone()
        return result


def get_proper_name(member_id):
    conn = get_db()
    with conn.cursor() as curr:
        stmt = "select name, gender from member where id = %s"
        result = curr.execute(stmt, (member_id,)).fetchone()

    if result[1][0] == 'M':
        surname = '先生'
    else:
        surname = '小姐'
    return result[0][0] + surname


def get_name(member_id):
    conn = get_db()
    with conn.cursor() as curr:
        stmt = "select name from member where id = %s;"
        result = curr.execute(stmt, (member_id,)).fetchone()[0]
        return result


def get_r1_info(matching_id):
    conn = get_db()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT place1_url, place2_url, time1, time2, time3, comment
            FROM matching WHERE id = %s
        """, (matching_id,))
        row = cur.fetchone()
        return row


def change_state(current_state,
                 correct_state,
                 new_state,
                 matching_id,
                 conn=None,
                 commit=True):
    if ALLOW_CHANGE_STATE:
        if not conn:
            conn = get_db()
        # check state，如果有人不在正確的state，本次操作取消
        if current_state != correct_state:
            raise ValueError('狀態錯誤❌')

        with conn.cursor() as curr:
            stmt = """
            update matching set current_state = %s,
            last_change_state_at=now(),
            updated_at = now() where id=%s;
            """
            curr.execute(
                stmt, (new_state, matching_id,))

            stmt = """
            insert into matching_state_history (matching_id, old_state, new_state, created_at)
            values (%s, %s, %s, now());
            """
            curr.execute(
                stmt, (matching_id, current_state, new_state))
        if commit:
            conn.commit()


def store_confirm_data(confirm_data, matching_id, conn=None, commit=True):
    if ALLOW_CHANGE_VALUE:
        params = confirm_data.copy()
        params['matching_id'] = matching_id

        for key in ['time1', 'time2', 'time3']:
            if params.get(key) == '':
                params[key] = None

        update_stmt = """
            update matching set
            place1_url = %(place1_url)s,
            place2_url = %(place2_url)s,
            time1 = %(time1)s,
            time2 = %(time2)s,
            time3 = %(time3)s,
            comment = %(comment)s
            where id = %(matching_id)s
            """
        with conn.cursor() as curr:
            curr.execute(update_stmt, params)

        if commit:
            conn.commit()


def store_booking_data(booking_data, matching_id, conn=None, commit=True):
    if ALLOW_CHANGE_VALUE:
        params = booking_data.copy()
        params['matching_id'] = matching_id
        update_stmt = """
            update matching set
            book_phone = %(book_phone)s,
            book_name = %(book_name)s,
            comment = %(comment)s,
            selected_place = %(selected_place)s,
            selected_time = %(selected_time)s
            where id = %(matching_id)s
            """
        with conn.cursor() as curr:
            curr.execute(update_stmt, params)

        if commit:
            conn.commit()


@app.route('/<token>/<action>', methods=['GET'])
def router(token, action):
    # 先在這邊解析token，並導引至正確的動作
    session['action'] = action

    matching_info = get_token_matching(token)
    if matching_info:
        session['matching_info'] = matching_info
        session['obj_name'] = get_name(matching_info['object_id'])
        session['sub_name'] = get_name(matching_info['subject_id'])

        # 一些特別需要存的在這邊if就好

        # 直接在這邊放連結失效的error

        return redirect(url_for(action))

    else:
        return render_template('error.html', message='token錯誤❌')


@app.route('/<token>/sudden_change_time/<who>', methods=['GET', 'POST'])
def sudden_change_time(token, who):
    matching_info = get_token_matching(token)
    if who == 'sub':
        member_id = matching_info['subject_id']
    elif who == 'obj':
        member_id = matching_info['object_id']
    else:
        return render_template('error.html', message='錯誤❌')

    if request.method == 'POST':

        if matching_info['current_state'] not in ('dating_notification_sending'):
            return render_template('error.html', message='目前狀態無法使用超臨時改期❌，請聯絡客服做處理！')

        # insert change_time_message
        change_time_stmt = """
        insert into sudden_change_time_history
        (member_id, created_at, matching_id)
        values (%s, now(), %s)
        """

        change_state_stmt = """
        update matching set current_state = 'next_month_sending',
        last_change_state_at=now(),
        updated_at = now() where id = %s;
        """

        conn = get_db()

        with conn.cursor() as curr:
            curr.execute(change_time_stmt, (member_id,
                                            matching_info['id']))
            curr.execute(change_state_stmt, (matching_info['id'],))
        conn.commit()

        return render_template('thank_you.html',
                               header='已成功改期',
                               message=f"""
                               {get_proper_name(member_id)}已新增一筆超臨時改期紀錄<br>
                               此配對延後至下個月<br>
                               """)
    else:
        return render_template('confirm.html',
                               message=f"是否對{get_proper_name(member_id)}觸發超臨時改期？",
                               btn_name='確認改期',
                               action_url=url_for(
                                   'sudden_change_time', token=token, who=who),
                               alert='確定要觸發超臨時改期嗎？')


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

        # first check right state
        stmt = """
        select current_state from matching where id = %s;
        """

        if matching_info['current_state'] not in ('deal_1d_notification_sending', 'deal_3d_notification_sending'):
            return render_template('error.html', message='目前狀態無法改期❌，請聯絡客服做處理！')

        # insert change_time_message
        change_time_stmt = """
        insert into change_time_history
        (member_id, created_at, matching_id, change_time_message)
        values (%s, now(), %s, %s)
        """

        change_state_stmt = """
        update matching set current_state = 'change_time_notification_sending',
        last_change_state_at=now(),
        updated_at = now() where id = %s;
        """

        conn = get_db()
        with conn.cursor() as curr:
            curr.execute(change_time_stmt, (member_id,
                                            matching_info['id'], message))
            curr.execute(change_state_stmt, (matching_info['id'],))
        conn.commit()

        return render_template('thank_you.html',
                               header='您已成功改期',
                               message="""
                               本配對已成功改期<br>
                               系統將重新為您安排配對<br>
                               請耐心等待後續通知<br>
                               """)
    else:
        # 檢查這一對是否已經有改期過，如果有，顯示提醒訊息
        # if has_changed_time(matching_info['id']):
        #     return render_template('change_time.html', token=token, member_id=member_id, message="這一對已經有改期過了")
        return render_template('change_time.html', token=token, who=who,
                               link_endpoint=url_for(
                                   'sudden_change_time', token=token, who=who))


@app.route('/invitation', methods=['GET', 'POST'])
def invitation():
    matching_info = session.get('matching_info')
    if request.method == 'POST':
        try:
            change_state(matching_info['current_state'],
                         'invitation_waiting', 'liked_sending',
                         matching_info['id'])
        except ValueError as e:
            return render_template('error.html', message=str(e))
        return render_template('thank_you.html',
                               message="""
                               已傳送邀請給對方<br>
                                請耐心等待對方的回覆<br>
                                期待你們的美好相遇！
                               <br>
                               """,
                               header='✅您已傳送邀請')
    return render_template('confirm.html',
                           message=f"""
                           要傳送邀請給{get_proper_name(matching_info['object_id'])}嗎？
                           """,
                           header=f'傳送邀請',
                           btn_name='確認傳送',
                           action_url=url_for('invitation'))


@app.route('/liked', methods=['GET', 'POST'])
def liked():
    matching_info = session.get('matching_info')
    if request.method == 'POST':
        try:
            change_state(matching_info['current_state'],
                         'liked_waiting', 'rest_r1_sending',
                         matching_info['id'])
        except ValueError as e:
            return render_template('error.html', message=str(e))
        return render_template('thank_you.html',
                               header="✅您已確認相遇",
                               message="""
                               屬於你們的連結已悄然展開<br>
                               系統將安排接下來的約會流程<br>
                               讓浪漫的相遇在每個細節中綻放
                               <br>
                               """)
    return render_template('confirm.html',
                           message=f"""
                           {get_proper_name(matching_info['subject_id'])}對您傳送邀請<br>
                        是否確認相遇？<br>
                           """,
                           header='邀請回覆',
                           btn_name='確認相遇',
                           action_url=url_for('liked'))


@app.route('/choose_rest/<int:rest_round>', methods=['POST'])
def choose_rest(rest_round):
    '''
    只要是要選餐廳就會來這個route
    '''
    if request.method == 'POST':
        # Get form data
        if rest_round != 3:
            url1 = request.form['place1']
            url2 = request.form['place2']
            time1 = request.form['time1']
            time2 = request.form['time2']
            time3 = request.form['time3']
            comment = request.form.get('comment', '')
        else:
            url1 = session['confirm_data']['place1_url']
            url2 = session['confirm_data']['place2_url']
            time1 = session['confirm_data']['time1']
            time2 = session['confirm_data']['time2']
            time3 = session['confirm_data']['time3']
            comment = request.form.get('comment', '')

        # Store for confirmation step
        session['confirm_data'] = {
            'place1_url': url1,
            'place2_url': url2,
            'time1': time1,
            'time2': time2,
            'time3': time3,
            'comment': comment
        }

        places = [url1, url2]
        times = [time1, time2, time3]

        if rest_round == 1:
            first_word = """
            """
        else:
            first_word = ''
        return render_template('confirm_places.html',
                               places=places,
                               times=times,
                               comment=comment,
                               go_back_url=url_for(f'rest_r{rest_round}'),
                               confirm_url=url_for(
                                   'confirm_rest', rest_round=rest_round),
                               first_word=first_word)


@app.route('/confirm_rest/<int:rest_round>', methods=['POST'])
def confirm_rest(rest_round):
    data = session.get('confirm_data')
    matching_info = session.get('matching_info')
    try:
        conn = get_db()
        change_state(matching_info['current_state'],
                     f'rest_r{rest_round}_waiting',
                     f'rest_r{rest_round+1}_sending',
                     matching_info['id'],
                     conn=conn, commit=False)
        store_confirm_data(data, matching_info['id'],
                           conn=conn, commit=False)
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template('error.html', message=str(e))

    return render_template('thank_you.html',
                           header="✅成功送出餐廳選項",
                           message="""
                            系統將知會對方協助訂位<br>
                            請耐心等待系統通知<br>
                           """)


@app.route('/confirm_booking/<int:rest_round>', methods=['POST'])
def confirm_booking(rest_round):
    data = session.get('confirm_data')
    matching_info = session.get('matching_info')

    data['book_name'] = request.form['book_name']
    data['book_phone'] = request.form['book_phone']
    data['comment'] = request.form['comment']
    try:
        conn = get_db()
        change_state(matching_info['current_state'],
                     f'rest_r{rest_round}_waiting',
                     'deal_sending',
                     matching_info['id'],
                     conn=conn, commit=False)
        store_booking_data(data, matching_info['id'],
                           conn=conn, commit=False)
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template('error.html', message=str(e))

    return render_template('thank_you.html',
                           header="✅成功傳送訂位資訊",
                           message="""
                            感謝您成功訂位<br>
                            系統將通知雙方約會資訊<br>
                            祝您約會順利！<br>
                           """)


@app.route('/rest_r1', methods=['GET'])
def rest_r1():
    return render_template('submit_places.html',
                           post_to=url_for('choose_rest', rest_round=1),
                           dating_title='約會的餐廳和時間',
                           first_word="""
                           請提供心儀的餐廳選項和時間<br>
                           """,
                           second_word="""
                           """)


@app.route('/booking/<int:rest_round>', methods=['POST'])
def booking(rest_round):
    # Get form data
    selected_place = request.form['selected_place']
    selected_time = request.form['selected_time']

    # Store for confirmation step
    session['confirm_data'] = {
        'selected_place': selected_place,
        'selected_time': selected_time,
    }

    return render_template('booking_info.html',
                           place=selected_place,
                           time=selected_time,
                           go_back_url=url_for(f'rest_r{rest_round}'),
                           confirm_url=url_for('confirm_booking', rest_round=rest_round))


@app.route('/rest_r2', methods=['GET', 'POST'])
def rest_r2():
    '''
    第二輪，男方看到女生的提供的選項，要有勾選
    '''
    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])

    return render_template('show_places.html',
                           place1_url=r1_info['place1_url'],
                           place2_url=r1_info['place2_url'],
                           time1=r1_info['time1'],
                           time2=r1_info['time2'],
                           time3=r1_info['time3'],
                           booking_url=url_for('booking', rest_round=2),
                           cannot_url=url_for('rest_r2_reject'),
                           comment=r1_info['comment']
                           )


@app.route('/rest_r2/reject', methods=['GET', 'POST'])
def rest_r2_reject():
    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])
    session['confirm_data'] = r1_info

    return render_template('submit_places.html',
                           go_back_url=url_for('rest_r2'),
                           post_to=url_for('choose_rest', rest_round=2),
                           lock=True,
                           dating_title='重新選地方'
                           )


@app.route('/rest_r3', methods=['GET', 'POST'])
def rest_r3():
    '''
    第三輪，女方要勾的時間，沒了就沒了
    '''
    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])
    session['confirm_data'] = r1_info

    places = [r1_info['place1_url'], r1_info['place2_url']]
    times = [r1_info['time1'], r1_info['time2'], r1_info['time3']]

    return render_template('confirm_places.html',
                           places=places,
                           times=times,
                           comment=r1_info['comment'],
                           new_message=True,
                           cannot_url=url_for("bye_bye", rest_round=3),
                           confirm_url=url_for('choose_rest', rest_round=3))


@app.route('/rest_r4', methods=['GET', 'POST'])
def rest_r4():

    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])
    session['confirm_data'] = r1_info

    return render_template('show_places.html',
                           place1_url=r1_info['place1_url'],
                           place2_url=r1_info['place2_url'],
                           time1=r1_info['time1'],
                           time2=r1_info['time2'],
                           time3=r1_info['time3'],
                           comment=r1_info['comment'],
                           booking_url=url_for('booking', rest_round=4),
                           bye_bye_url=url_for('bye_bye', rest_round=4)
                           )


@app.route('/bye_bye/<int:rest_round>', methods=['GET', 'POST'])
def bye_bye(rest_round):

    matching_info = session.get('matching_info')
    try:
        conn = get_db()
        change_state(matching_info['current_state'],
                     f'rest_r{rest_round}_waiting',
                     'abort_sending',
                     matching_info['id'],
                     conn=conn)
    except ValueError as e:
        conn.rollback()
        return render_template('error.html', message=str(e))

    return render_template('thank_you.html',
                           message='流局！')


# ============================================================================
# MOCK ENDPOINTS FOR ALL TEMPLATES
# ============================================================================


@app.route("/mock/error", methods=["GET"])
def mock_error():
    """
    Mock endpoint for error.html template
    """
    return render_template(
        "error.html", message="這是一個模擬的錯誤訊息，用於測試錯誤頁面的顯示效果。"
    )


@app.route("/mock/show_places", methods=["GET"])
def mock_show_places():
    """
    Mock endpoint for show_places.html template
    """
    return render_template(
        "show_places.html",
        place1_url="https://maps.google.com/?q=台北市信義區松仁路100號",
        place2_url="https://maps.google.com/?q=台北市大安區忠孝東路四段1號",
        time1="2024年12月25日 晚上7:00",
        time2="2024年12月26日 晚上6:30",
        time3="2024年12月27日 晚上8:00",
        booking_url=url_for("mock_booking_info"),
        cannot_url=url_for("mock_submit_places"),
        bye_bye_url=url_for("mock_bye_bye"),
        comment="希望能在浪漫的氛圍中度過美好的時光",
    )


@app.route("/mock/submit_places", methods=["GET"])
def mock_submit_places():
    """
    Mock endpoint for submit_places.html template
    """
    return render_template(
        "submit_places.html",
        dating_title="提交約會地點與時間",
        first_word="請提供您心儀的餐廳選項和時間安排",
        post_to=url_for("mock_confirm_places"),
        go_back_url=url_for("mock_show_places"),
        lock=False,
    )


@app.route("/mock/submit_places_locked", methods=["GET"])
def mock_submit_places_locked():
    """
    Mock endpoint for submit_places.html template with locked fields
    """
    return render_template(
        "submit_places.html",
        dating_title="重新選地方",
        first_word="請重新提供餐廳選項",
        post_to=url_for("mock_confirm_places"),
        go_back_url=url_for("mock_show_places"),
        lock=True,
    )


@app.route("/mock/thank_you", methods=["GET"])
def mock_thank_you():
    """
    Mock endpoint for thank_you.html template
    """
    return render_template(
        "thank_you.html",
        header="✅操作成功完成",
        message="""
                            感謝您的參與<br>
                            系統將處理您的請求<br>
                            請耐心等待後續通知<br>
                           """,
    )


@app.route("/mock/confirm", methods=["GET"])
def mock_confirm():
    """
    Mock endpoint for confirm.html template
    """
    return render_template(
        "confirm.html",
        header="確認操作",
        message="您確定要執行此操作嗎？",
        action_url=url_for("mock_thank_you"),
        btn_name="確認執行",
    )


@app.route("/mock/confirm_places", methods=["GET"])
def mock_confirm_places():
    """
    Mock endpoint for confirm_places.html template
    """
    return render_template(
        "confirm_places.html",
        message="請確認以下約會資訊",
        first_word="確認無誤後請點擊確認送出",
        places=[
            "https://maps.google.com/?q=台北市信義區松仁路100號",
            "https://maps.google.com/?q=台北市大安區忠孝東路四段1號",
        ],
        times=[
            "2024年12月25日 晚上7:00",
            "2024年12月26日 晚上6:30",
            "2024年12月27日 晚上8:00",
        ],
        comment="希望能在浪漫的氛圍中度過美好的時光",
        confirm_url=url_for("mock_thank_you"),
        go_back_url=url_for("mock_submit_places"),
        cannot_url=url_for("mock_bye_bye"),
        new_message=False,
    )


@app.route("/mock/confirm_places_with_comment", methods=["GET"])
def mock_confirm_places_with_comment():
    """
    Mock endpoint for confirm_places.html template with comment field
    """
    return render_template(
        "confirm_places.html",
        message="請確認以下約會資訊",
        first_word="確認無誤後請點擊確認送出",
        places=[
            "https://maps.google.com/?q=台北市信義區松仁路100號",
            "https://maps.google.com/?q=台北市大安區忠孝東路四段1號",
        ],
        times=[
            "2024年12月25日 晚上7:00",
            "2024年12月26日 晚上6:30",
            "2024年12月27日 晚上8:00",
        ],
        comment="希望能在浪漫的氛圍中度過美好的時光",
        confirm_url=url_for("mock_thank_you"),
        go_back_url=url_for("mock_submit_places"),
        cannot_url=url_for("mock_bye_bye"),
        new_message=True,
    )


@app.route("/mock/booking_info", methods=["GET"])
def mock_booking_info():
    """
    Mock endpoint for booking_info.html template
    """
    return render_template(
        "booking_info.html",
        place="https://maps.google.com/?q=台北市信義區松仁路100號",
        time="2024年12月25日 晚上7:00",
        go_back_url=url_for("mock_show_places"),
        confirm_url=url_for("mock_confirm_booking"),
    )


@app.route("/mock/bye_bye", methods=["GET"])
def mock_bye_bye():
    """
    Mock endpoint for ending the matching process
    """
    return render_template(
        "thank_you.html",
        header="❌配對結束",
        message="很抱歉，此次配對流程已結束。",
    )


# ============================================================================
# MOCK FORM HANDLERS
# ============================================================================


@app.route("/mock/confirm_booking", methods=["POST"])
def mock_confirm_booking():
    """
    Mock endpoint for confirming booking
    """
    return render_template(
        "thank_you.html",
        header="✅成功傳送訂位資訊",
        message="""
                            感謝您成功訂位<br>
                            系統將通知雙方約會資訊<br>
                            祝您約會順利！<br>
                           """,
    )


@app.route("/mock/process_places", methods=["POST"])
def mock_process_places():
    """
    Mock endpoint for processing place submission
    """
    return redirect(url_for("mock_confirm_places"))


@app.route("/mock/process_confirmation", methods=["POST"])
def mock_process_confirmation():
    """
    Mock endpoint for processing confirmation
    """
    return redirect(url_for("mock_thank_you"))


if __name__ == '__main__':
    app.run(debug=True)

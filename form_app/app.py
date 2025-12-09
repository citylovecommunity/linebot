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
        stmt = "select * from matching where access_token = %s;"
        result = curr.execute(stmt, (token,)).fetchone()
        return result


def get_current_state(matching_id):
    conn = get_db()
    with conn.cursor() as curr:
        stmt = "select current_state from matching where id = %s;"
        result = curr.execute(stmt, (matching_id,)).fetchone()
        return result[0] if result else None


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
            SELECT place1_url, place2_url, date1, date2, date3, comment
            FROM matching WHERE id = %s
        """, (matching_id,))
        row = cur.fetchone()
        return row


def change_state(correct_state,
                 new_state,
                 matching_id):

    conn = get_db()
    try:
        current_state = get_current_state(matching_id)

        if isinstance(correct_state, tuple):
            if current_state not in correct_state:
                raise ValueError("沒有支援的type")
        elif isinstance(correct_state, str):
            if current_state != correct_state:
                raise ValueError("沒有支援的type")
        else:
            raise ValueError("沒有支援的type")

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

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e


@app.route('/<token>/<action>', methods=['GET'])
def router(token, action):
    # 先在這邊解析token，並導引至正確的動作
    session['action'] = action

    matching_info = get_token_matching(token)
    if matching_info:
        session['matching_info'] = matching_info
        session['obj_name'] = get_name(matching_info['object_id'])
        session['sub_name'] = get_name(matching_info['subject_id'])
        return redirect(url_for(action))
    else:
        return render_template('error.html', message='token錯誤❌')


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


@app.route('/invitation', methods=['GET', 'POST'])
def invitation():
    matching_info = session.get('matching_info')
    name = get_proper_name(matching_info['object_id'])
    if request.method == 'POST':
        try:
            change_state('invitation_waiting', 'liked_sending',
                         matching_info['id'])
        except ValueError as e:
            pass
        return render_template('thank_you.html',
                               message="""
                               已傳送邀請給對方<br>
                                請耐心等待對方的回覆<br>
                                期待你們的美好相遇！
                               <br>
                               """,
                               header='✅您已傳送邀請')
    return render_template('confirm.html',
                           header='赴約意願確認',
                           message=f"""
                           有意願認識{name}這位新朋友嗎？
                           """,
                           btn_name='願意認識新朋友',
                           action_url=url_for('invitation'))


@app.route('/liked', methods=['GET', 'POST'])
def liked():
    matching_info = session.get('matching_info')
    name = get_proper_name(matching_info['subject_id'])
    if request.method == 'POST':
        try:
            change_state('liked_waiting', 'rest_r1_sending',
                         matching_info['id'])
        except ValueError as e:
            pass
        return render_template('thank_you.html',
                               header="✅您已確認相遇",
                               message="""
                            屬於你們的連結已悄然展開<br>我們將安排接下來的約會流程<br>讓浪漫的相遇在每個細節中綻放
                            """)

    return render_template('confirm.html',
                           message=f"""{name}有意願認識您<br>你們的匹配程度有{matching_info['grading_metric']}分！<br>是否要交個朋友呢？""",
                           header='邀請回覆',
                           btn_name='可以',
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
            date1 = request.form['date1']
            date2 = request.form['date2']
            date3 = request.form['date3']
            comment = request.form.get('comment', '')
        else:
            url1 = session['confirm_data']['place1_url']
            url2 = session['confirm_data']['place2_url']
            date1 = session['confirm_data']['date1']
            date2 = session['confirm_data']['date2']
            date3 = session['confirm_data']['date3']
            comment = request.form.get('comment', '')

        # Store for confirmation step
        session['confirm_data'] = {
            'place1_url': url1,
            'place2_url': url2,
            'date1': date1,
            'date2': date2,
            'date3': date3,
            'comment': comment
        }

        places = [url1, url2]
        dates = [date1, date2, date3]

        return render_template('confirm_places.html',
                               places=places,
                               dates=dates,
                               comment=comment,
                               go_back_url=url_for(f'rest_r{rest_round}'),
                               confirm_url=url_for(
                                   'confirm_rest', rest_round=rest_round),
                               header="確認地點日期",
                               message="""
                               送出之前<br>
                               請確認地點和日期是否正確
                               """)


@app.route('/confirm_rest/<int:rest_round>', methods=['POST'])
def confirm_rest(rest_round):

    def store_confirm_data(confirm_data, matching_id):

        conn = get_db()
        try:
            params = confirm_data.copy()
            params['matching_id'] = matching_id

            for key in ['date1', 'date2', 'date3']:
                if params.get(key) == '':
                    params[key] = None

            update_stmt = """
                    update matching set
                    place1_url = %(place1_url)s,
                    place2_url = %(place2_url)s,
                    date1 = %(date1)s,
                    date2 = %(date2)s,
                    date3 = %(date3)s,
                    comment = %(comment)s
                    where id = %(matching_id)s
                    """
            with conn.cursor() as curr:
                curr.execute(update_stmt, params)
            conn.commit()
        except Exception as e:
            raise e
    data = session.get('confirm_data')
    matching_info = session.get('matching_info')
    try:
        change_state(f'rest_r{rest_round}_waiting',
                     f'rest_r{rest_round+1}_sending',
                     matching_info['id'])
        store_confirm_data(data, matching_info['id'])
    except ValueError as e:
        pass

    return render_template('thank_you.html',
                           header="✅成功送出餐廳選項",
                           message="""
                            我們將知會對方協助訂位<br>
                            請耐心等待後續通知<br>
                           """)


@app.route('/confirm_booking/<int:rest_round>', methods=['POST'])
def confirm_booking(rest_round):

    def store_booking_data(booking_data, matching_id):

        conn = get_db()
        try:
            params = booking_data.copy()
            # params['book_time'] = datetime.strptime(
            #     params['book_time'], '%H:%M')
            # params['book_time'] = pytz.timezone(
            #     'Asia/Taipei').localize(params['book_time'])

            params['matching_id'] = matching_id
            update_stmt = """
                    update matching set
                    book_phone = %(book_phone)s,
                    book_name = %(book_name)s,
                    book_time = %(book_time)s,
                    comment = %(comment)s,
                    selected_place = %(selected_place)s,
                    selected_date = %(selected_date)s
                    where id = %(matching_id)s
                    """
            with conn.cursor() as curr:
                curr.execute(update_stmt, params)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
    data = session.get('confirm_data')
    matching_info = session.get('matching_info')

    data['book_name'] = request.form['book_name']
    data['book_time'] = request.form['book_time']
    data['book_phone'] = request.form['book_phone']
    data['comment'] = request.form['comment']
    try:
        change_state(f'rest_r{rest_round}_waiting',
                     'deal_sending',
                     matching_info['id'])
        store_booking_data(data, matching_info['id'])
    except ValueError as e:
        pass

    return render_template('thank_you.html',
                           header="✅成功傳送訂位資訊",
                           message="""
                            感謝您成功訂位<br>
                            我們將通知雙方約會資訊<br>
                            祝您約會順利！<br>
                           """)


@app.route('/rest_r1', methods=['GET'])
def rest_r1():

    return render_template('submit_places.html',
                           post_to=url_for('choose_rest', rest_round=1),
                           header='約會的餐廳和日期',
                           message="""
                           請提供心儀的餐廳選項和日期<br>
                           餐廳請複製貼上Google Map網址<br>
                           <br>
                           若有額外需求（如幾點後方便）<br>
                           請在底下留言
                           <br>
                           我們將會把您提供的餐廳日期轉達給對方
                           <br>
                           <br>
                           """,
                           )


@app.route('/booking/<int:rest_round>', methods=['POST'])
def booking(rest_round):
    # Get form data
    selected_place = request.form['selected_place']
    selected_date = request.form['selected_date']

    # Store for confirmation step
    session['confirm_data'] = {
        'selected_place': selected_place,
        'selected_date': selected_date,
    }

    return render_template('booking_info.html',
                           place=selected_place,
                           date=selected_date,
                           go_back_url=url_for(f'rest_r{rest_round}'),
                           confirm_url=url_for(
                               'confirm_booking', rest_round=rest_round),
                           header='請協助餐廳訂位',
                           message="""
                           請協助預約所選的約會餐廳<br>
                           <br>
                           若日期或時間不符合對方需求<br>
                           請返回上一頁點選紅色按鈕進行修改
                           """)


@app.route('/rest_r2', methods=['GET', 'POST'])
def rest_r2():
    '''
    第二輪，男方看到女生的提供的選項，要有勾選
    '''
    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])

    places = [r1_info['place1_url'], r1_info['place2_url']]
    dates = [r1_info['date1'], r1_info['date2'], r1_info['date3']]

    return render_template('show_places.html',
                           places=places,
                           dates=dates,
                           booking_url=url_for('booking', rest_round=2),
                           cannot_url=url_for('rest_r2_reject'),
                           comment=r1_info['comment'],
                           header="餐廳時間勾選",
                           message="""
                           以下是女方提供的餐廳以及方便的日期<br>
                           勾選完成後按下藍色按鈕進入訂位畫面<br>
                           若時間或地點不方便，請點選紅色按鈕
                           """
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
                           header='重新勾選餐廳或時間',
                           message="""
                           點按重填按鈕<br>
                           重新填入自己方便的時間或地點<br>
                           並麻煩將重新填寫的原因也寫下<br>
                           我們將會轉達給女方作確認
                           """
                           )


@app.route('/rest_r3', methods=['GET', 'POST'])
def rest_r3():

    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])
    session['confirm_data'] = r1_info

    places = [r1_info['place1_url'], r1_info['place2_url']]
    dates = [r1_info['date1'], r1_info['date2'], r1_info['date3']]

    return render_template('confirm_places.html',
                           places=places,
                           dates=dates,
                           comment=r1_info['comment'],
                           new_message=True,
                           cannot_url=url_for("bye_bye"),
                           confirm_url=url_for('choose_rest', rest_round=3),
                           header="""
                           餐廳地點的選擇
                           """,
                           message="""
                           由於上次您提交的地點/時間有部分原因男無法配合<br>
                           以下是男方所提交的餐廳和時間<br>
                           再麻煩協助確認<br>
                           也可以在留言區直接跟男方說比較偏好的地點/時間
                           """)


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
                           bye_bye_url=url_for('bye_bye'),
                           header="""
                           餐廳地點的選擇
                           """,
                           message="""
                           您上次重新選擇的時間地點已被女方所確認<br>
                            沒問題的話再按下藍色按鈕進入訂餐廳頁面
                           """
                           )


@app.route('/bye_bye', methods=['GET', 'POST'])
def bye_bye():
    # 改狀態，弄到下次再說
    matching_info = session.get('matching_info')
    try:
        change_state(('rest_r3_waiting', 'rest_r4_waiting'),
                     'next_time_sending', matching_info['id'])
    except ValueError as e:
        pass
    return render_template(
        'thank_you.html',
        header='下次再約',
        message="""
        本約會將移至下回安排<br>
        再請留意接下來的資訊：）
        """
    )


@app.route("/version")
def version():
    return {"version": "v1.2.3", "build": "2025-12-09T16:00:00Z"}


if __name__ == '__main__':
    app.run(debug=True)

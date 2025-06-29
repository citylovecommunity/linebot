import datetime
from email import message
import os
import urllib.parse

import psycopg
from flask import Flask, redirect, render_template, request, session, url_for
from psycopg.rows import dict_row

app = Flask(__name__)
app.secret_key = 'secret'
DB = os.getenv('DB')


def get_token_matching(token, conn):
    with conn.cursor(row_factory=dict_row) as curr:
        stmt = "select id, subject_id, object_id from matching where access_token = %s;"
        result = curr.execute(stmt, (token,)).fetchone()
        return result


def get_name(member_id, conn):
    with conn.cursor() as curr:
        stmt = "select name from member where id = %s;"
        result = curr.execute(stmt, (member_id,)).fetchone()[0]
        return result


def change_state(correct_state, new_state, matching_id, conn):
    with conn.cursor() as curr:
        # check state，如果有人不在正確的state，本次操作取消
        state_stmt = "select TRUE from matching where id = %s and current_state <> %s;"
        check = curr.execute(
            state_stmt, (matching_id, correct_state)).fetchone()
        if check:
            return render_template('error.html', message='狀態錯誤❌')
        stmt = "update matching set current_state = %s where id=%s;"
        curr.execute(
            stmt, (new_state, matching_id))


# TODO: 每一個操作都在這裡，出發
@app.route('/<token>/<action>', methods=['GET'])
def router(token, action):
    # 先在這邊解析token，並導引至正確的動作
    session['action'] = action
    with psycopg.connect(DB) as conn:
        matching_info = get_token_matching(token, conn)
        if matching_info:
            session['matching_info'] = matching_info

            session['obj_name'] = get_name(matching_info['object_id'], conn)
            session['sub_name'] = get_name(matching_info['subject_id'], conn)

            # 一些特別需要存的在這邊if就好

            # 直接在這邊放連結失效的error

            return redirect(url_for(action))

        else:
            return render_template('error.html', message='token錯誤❌')


@app.route('/invitation', methods=['GET', 'POST'])
def invitation():
    matching_info = session.get('matching_info')
    if request.method == 'POST':

        with psycopg.connect(DB) as conn:
            result = change_state('invitation_waiting', 'liked_sending',
                                  matching_info['id'], conn)
            if result:
                return result
            return render_template('thank_you.html',
                                   message="您的like已經傳送給對方👍")
    return render_template('confirm.html',
                           message=f'您是否同意傳送like給{session['obj_name']}',
                           header='邀請確認')


@app.route('/liked', methods=['GET', 'POST'])
def liked():
    matching_info = session.get('matching_info')
    if request.method == 'POST':

        with psycopg.connect(DB) as conn:
            result = change_state('liked_waiting', 'rest_r1_sending',
                                  matching_info['id'], conn)
            if result:
                return result
            return render_template('thank_you.html',
                                   message="已成功配對💓")
    return render_template('confirm.html',
                           message=f'您是否想認識{session['sub_name']}',
                           header='被like確認')


@app.route('/submit_places', methods=['GET', 'POST'])
def submit_places():
    matching_info = session.get('matching_info')
    if request.method == 'POST':
        # Get form data
        url1 = request.form['place1']
        url2 = request.form['place2']
        time1 = request.form['time1']
        time2 = request.form['time2']
        time3 = request.form['time3']

        def extract_query_name(url):
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query).get('q')
            return query[0] if query else url

        place1_name = extract_query_name(url1)
        place2_name = extract_query_name(url2)

        # Store for confirmation step
        session['confirm_data'] = {
            'place1_url': url1,
            'place2_url': url2,
            'place1_name': place1_name,
            'place2_name': place2_name,
            'time1': time1,
            'time2': time2,
            'time3': time3
        }

        return render_template('confirm_places.html',
                               place1_url=url1,
                               place2_url=url2,
                               place1_name=place1_name,
                               place2_name=place2_name,
                               time1=time1,
                               time2=time2,
                               time3=time3)
    return render_template('submit_places.html')


@app.route('/confirm-places', methods=['POST'])
def confirm_places():
    data = session.get('confirm_data')
    if not data:
        return redirect(url_for('submit_places'))

    # Save to DB or log here
    print("Confirmed submission:", data)

    return redirect(url_for('thank_you'))


if __name__ == '__main__':
    app.run(debug=True)

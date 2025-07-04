
import os


import psycopg
from flask import Flask, redirect, render_template, request, session, url_for, g
from psycopg.rows import dict_row

app = Flask(__name__)
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
        stmt = "select id, subject_id, object_id, current_state from matching where access_token = %s;"
        result = curr.execute(stmt, (token,)).fetchone()
        return result


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


def get_r2_info(matching_id):
    conn = get_db()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT selected_place, time1, time2, time3, comment
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
    if not conn:
        conn = get_db()
    # check state，如果有人不在正確的state，本次操作取消
    if current_state != correct_state:
        raise ValueError('狀態錯誤❌')

    with conn.cursor() as curr:
        stmt = "update matching set current_state = %s where id=%s;"
        curr.execute(
            stmt, (new_state, matching_id))
    if commit:
        conn.commit()


def store_confirm_data(confirm_data, matching_id, conn=None, commit=True):
    params = confirm_data.copy()
    params['matching_id'] = matching_id
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
                               message="您的like已經傳送給對方👍")
    return render_template('confirm.html',
                           message=f'您是否同意傳送like給{session['obj_name']}',
                           header='邀請確認')


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
                               message="已成功配對💓")
    return render_template('confirm.html',
                           message=f'您是否想認識{session['sub_name']}',
                           header='被like確認')


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

        return render_template('confirm_places.html',
                               places=places,
                               times=times,
                               comment=comment,
                               go_back_url=url_for(f'rest_r{rest_round}'),
                               confirm_url=url_for(
                                   'confirm_rest', rest_round=rest_round))


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
                           message='已傳送餐廳時間選項給對方')


@app.route('/rest_r1', methods=['GET'])
def rest_r1():

    return render_template('submit_places.html', post_to=url_for('choose_rest', rest_round=1))


@app.route('/rest_r2', methods=['GET', 'POST'])
def rest_r2():
    '''
    第二輪，男方看到女生的提供的選項，要有勾選
    '''
    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])
    if request.method == 'POST':
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
                               go_back_url=url_for('rest_r2'),
                               confirm_url=url_for('rest_r2_confirm'))
    return render_template('show_places.html',
                           place1_url=r1_info['place1_url'],
                           place2_url=r1_info['place2_url'],
                           time1=r1_info['time1'],
                           time2=r1_info['time2'],
                           time3=r1_info['time3'],
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
                           post_to=url_for('choose_rest', rest_round=2))


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

    places = [r1_info['place1_url'], r1_info['place2_url']]
    times = [r1_info['time1'], r1_info['time2'], r1_info['time3']]

    return render_template('show_places.html',
                           place1_url=r1_info['place1_url'],
                           place2_url=r1_info['place2_url'],
                           time1=r1_info['time1'],
                           time2=r1_info['time2'],
                           time3=r1_info['time3'],
                           comment=r1_info['comment'],
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


if __name__ == '__main__':
    app.run(debug=True)

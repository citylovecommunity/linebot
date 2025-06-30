
import os


import psycopg
from flask import Flask, redirect, render_template, request, session, url_for, g
from psycopg.rows import dict_row

app = Flask(__name__)
app.secret_key = 'secret'
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


def change_state(current_state,
                 correct_state,
                 new_state,
                 matching_id,
                 conn=get_db(),
                 commit=True):
    # check state，如果有人不在正確的state，本次操作取消
    if current_state != correct_state:
        raise ValueError('狀態錯誤❌')

    with conn.cursor() as curr:
        stmt = "update matching set current_state = %s where id=%s;"
        curr.execute(
            stmt, (new_state, matching_id))
    if commit:
        conn.commit()


def store_r1_info(confirm_data, matching_id, conn=get_db(), commit=True):

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


@app.route('/rest_r1', methods=['GET', 'POST'])
def rest_r1():
    '''
    第一輪，女方要填的網頁連結，需提供三個時間，兩個地點，一段留言
    感覺confirm_places可以混著後面rest_r2使用
    '''
    if request.method == 'POST':
        # Get form data
        url1 = request.form['place1']
        url2 = request.form['place2']
        time1 = request.form['time1']
        time2 = request.form['time2']
        time3 = request.form['time3']
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

        return render_template('confirm_places.html',
                               place1_url=url1,
                               place2_url=url2,
                               time1=time1,
                               time2=time2,
                               time3=time3,
                               comment=comment)
    return render_template('submit_places.html')


@app.route('/rest_r1/confirm', methods=['POST'])
def rest_r1_confirm():
    data = session.get('confirm_data')
    if not data:
        return redirect(url_for('submit_places'))

    matching_info = session.get('matching_info')
    try:
        conn = get_db()
        change_state(matching_info['current_state'],
                     'rest_r1_waiting',
                     'rest_r2_sending',
                     matching_info['id'],
                     conn=conn, commit=False)
        store_r1_info(data, matching_info['id'],
                      conn=conn, commit=False)
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template('error.html', message=str(e))

    return render_template('thank_you.html',
                           message='已傳送餐廳時間選項給對方')


if __name__ == '__main__':
    app.run(debug=True)

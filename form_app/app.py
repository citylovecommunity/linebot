import datetime
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


def get_obj_name(member_id, conn):
    with conn.cursor() as curr:
        stmt = "select name from member where id = %s;"
        result = curr.execute(stmt, (member_id,)).fetchone()[0]
        return result


@app.route('/submit-places', methods=['GET', 'POST'])
def submit_places():
    if request.method == 'POST':
        url1 = request.form.get('place1')
        url2 = request.form.get('place2')

        # Extract "query" from the URL to build a static iframe (simple solution)
        def extract_query(url):
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query).get('q')
            return query[0] if query else None

        place_query_1 = extract_query(url1)
        place_query_2 = extract_query(url2)

        return render_template(
            'submit_places.html',
            place1=url1,
            place2=url2,
            embed1=place_query_1,
            embed2=place_query_2,
            confirmed=False
        )

    return render_template('submit_places.html', confirmed=False)


@app.route('/confirm-places', methods=['POST'])
def confirm_places():
    # Record the confirmation
    with open("place_confirmations.txt", "a") as f:
        f.write(f"Places confirmed at {datetime.datetime.now()}\n")
    return redirect(url_for('thank_you'))


# TODO: 每一個操作都在這裡，出發
@app.route('/<token>/<action>', methods=['GET'])
def router(token, action):
    # 先在這邊解析token，並導引至正確的動作
    with psycopg.connect(DB) as conn:
        matching_info = get_token_matching(token, conn)
        if matching_info:
            session['matching_info'] = matching_info
            obj_name = get_obj_name(matching_info['object_id'], conn)
            session['obj_name'] = obj_name

            if action == 'invitation':
                return redirect(url_for('invitation'))

            else:
                return redirect(url_for('error'))

        else:
            return redirect(url_for('error'))


@app.route('/invitation', methods=['GET'])
def invitation():
    pass


@app.route('/confirm', methods=['POST'])
def confirm_post():
    # Here you record the confirmation
    matching_info = session.get('matching_info')
    with psycopg.connect(DB) as conn:
        with conn.cursor() as curr:
            # check state，如果有人不在正確的state，本次操作取消
            state_stmt = "select TRUE from matching where id = %s and current_state <> 'invitation_sending';"
            check = curr.execute(
                state_stmt, (matching_info['id'],)).fetchone()
            if check:
                redirect(url_for('error'))
            stmt = "update matching set current_state = 'invitation_waiting' where id=%s;"
            curr.execute(
                stmt, (matching_info['id'],))

    return redirect(url_for('thank_you'))


@app.route('/error', methods=['GET'])
def error():
    return render_template('error.html')


@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html', message="您的like已經傳送給對方👍")


if __name__ == '__main__':
    app.run(debug=True)

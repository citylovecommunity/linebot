from flask import (Blueprint, redirect, render_template, request, session,
                   url_for)
from flask_wtf import FlaskForm
from services.matching_services import (change_state,
                                        get_matching_info_from_token,
                                        get_proper_name)
from wtforms import (DateField, HiddenField, StringField, TextAreaField,
                     ValidationError)

from database import get_db
from wtforms.validators import URL, DataRequired, Optional

from shared.database.models import Matching

restaurant_bp = Blueprint('restaurant_bp', __name__)


class RestForm(FlaskForm):
    # --- Place 1 ---
    # 1. The visible text box (User types here)
    place1_name = StringField('第1間餐廳', validators=[DataRequired()])

    # 2. The hidden ID (JS fills this automatically)
    place1_id = StringField('Place 1 ID', validators=[DataRequired("請從清單中搜尋")])

    # --- Place 2 ---
    place2_name = StringField('第2間餐廳', validators=[Optional()])  # Optional
    place2_id = StringField('Place 2 ID')

    def validate_place2_id(self, field):
        # Check if the user typed something in the Name field
        name_has_data = bool(
            self.place2_name.data and self.place2_name.data.strip())

        # Check if the ID field is empty
        id_is_empty = not field.data or not field.data.strip()

        # Logic: If Name is filled BUT ID is empty -> Error
        if name_has_data and id_is_empty:
            raise ValidationError("請從清單中選取第 2 間餐廳")

    # Date 1 is required, others optional
    date1 = DateField('日期1', validators=[DataRequired()])
    date2 = DateField('日期2', validators=[Optional()])
    date3 = DateField('日期3', validators=[Optional()])

    # Use TextAreaField for the comment box
    comment = TextAreaField('留言給對方', validators=[DataRequired()])


@restaurant_bp.route('/choose_rest/<int:rest_round>/<token>', methods=['POST'])
def choose_rest(rest_round, token):
    form = RestForm()
    url1 = request.form['place1']
    url2 = request.form['place2']
    date1 = request.form['date1']
    date2 = request.form['date2']
    date3 = request.form['date3']
    comment = request.form.get('comment', '')

    places = [url1, url2]
    dates = [date1, date2, date3]

    return render_template('confirm_places.html',
                           places=places,
                           dates=dates,
                           comment=comment,
                           go_back_url=url_for(
                               f'.rest_r{rest_round}', token=token),
                           confirm_url=url_for(
                               '.confirm_rest', rest_round=rest_round, token=token),
                           header="確認地點日期",
                           message="""
                            送出之前，請確認地點和日期是否正確
                            """)


@restaurant_bp.route('/confirm_rest/<int:rest_round>/<token>', methods=['POST'])
def confirm_rest(rest_round, token):
    matching = get_matching_info_from_token(token)

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


@restaurant_bp.route('/confirm_booking/<int:rest_round>', methods=['POST'])
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


@restaurant_bp.route('/choose_restaurant_and_date/<token>', methods=['GET', 'POST'])
def choose_restaurant_and_date(token):
    # If there is data in session (user clicked "Back" from confirm page),
    # load it. Otherwise, load empty form.
    matching = get_matching_info_from_token(token)

    # Step 1: Initialize form_data from Session (Highest Priority)
    # This happens if user clicked "Back" or "Edit" from a confirmation page
    form_data = session.get('form_data', None)

    # Step 2: If Session is empty, try loading from Database (Fallback)

    if not form_data:
        form_data = {
            'place1_name': matching.place1_name,
            'place1_id': matching.place1_id,
            'place2_name': matching.place2_name,
            'place2_id': matching.place2_id,
            'date1': matching.date1,
            'date2': matching.date2,
            'date3': matching.date3,
        }

    if form_data['date1']:
        from dateutil import parser
        for i in range(1, 4):
            date_str = form_data[f'date{i}']
            if date_str:
                form_data[f'date{i}'] = parser.parse(date_str)

    form = RestForm(data=form_data)

    if form.validate_on_submit():
        # Store raw data in session
        session['form_data'] = form.data
        return redirect(url_for('.confirm', token=token))

    return render_template('choose_restaurant_and_date.html',
                           header='約會的餐廳和日期',
                           message="""
                           請提供心儀的餐廳選項和日期<br>
                           餐廳請直接在欄位搜尋
                           <br>
                           若有額外需求（如幾點後方便），請在底下留言
                           <br>
                           我們將會把您提供的餐廳日期轉達給對方
                           <br>
                           """,
                           form=form
                           )


@restaurant_bp.route('/confirm/<token>', methods=['GET', 'POST'])
def confirm(token):
    # Check if data exists in session; if not, kick them back to start
    if 'form_data' not in session:
        return redirect(url_for('.choose_restaurant_and_date'))

    # Load data from session to display it
    data = session['form_data']
    matching = get_matching_info_from_token(token)

    if request.method == 'POST':

        session = get_db()

        matching.place1_name = data['place1_name']
        matching.place1_id = data['place1_id']
        matching.place2_name = data['place2_name']
        matching.place2_id = data['place2_id']
        matching.date1 = data['date1']

        matching.date2 = data['date2']
        matching.date3 = data['date3']

        change_state('restaurant_choosing',
                     'restaurant_choosing_done', matching)
        session.commit()
        # Clear the session to prevent duplicate submissions
        session.pop('form_data', None)

        return render_template('thank_you.html',
                               header="✅成功送出餐廳選項",
                               message="""
                            我們將知會對方協助訂位<br>
                            請耐心等待後續通知<br>
                           """)

    # return render_template('confirm.html', data=data)
    return render_template('confirm_places.html',
                           data=data,
                           go_back_url=url_for(
                               '.choose_restaurant_and_date', token=token),
                           header="確認地點日期",
                           message="""
                            送出之前，請確認地點和日期是否正確
                            """)


@restaurant_bp.route('/booking/<int:rest_round>', methods=['POST'])
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


@restaurant_bp.route('/rest_r2', methods=['GET', 'POST'])
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


@restaurant_bp.route('/rest_r2/reject', methods=['GET', 'POST'])
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


@restaurant_bp.route('/rest_r3', methods=['GET', 'POST'])
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


@restaurant_bp.route('/rest_r4', methods=['GET', 'POST'])
def rest_r4():

    matching_info = session.get('matching_info')
    r1_info = get_r1_info(matching_info['id'])
    session['confirm_data'] = r1_info
    places = [r1_info['place1_url'], r1_info['place2_url']]
    dates = [r1_info['date1'], r1_info['date2'], r1_info['date3']]

    return render_template('show_places.html',
                           places=places,
                           dates=dates,
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

from decorators import match_transaction
from flask import Blueprint, render_template, request, url_for, flash, redirect
from services.matching_services import (change_state,
                                        get_introduction_link, get_blind_introduction_link,
                                        get_proper_name, error_page)
from shared.database.models import Matching

bp = Blueprint('show_confirmation_bp', __name__)


@bp.route('/invitation/<token>', methods=['GET', 'POST'])
@match_transaction
def invitation(matching: Matching):
    name = get_proper_name(matching.object.name, matching.object.gender)
    if request.method == 'POST':
        action = request.form.get("action")
        try:
            if action == 'accept':
                change_state(
                    ('invitation_waiting', 'invitation_rejected'), 'invitation_accepted', matching)
            elif action == 'reject':
                change_state(
                    ('invitation_waiting', 'invitation_accepted'), 'invitation_rejected', matching)
        except ValueError:
            flash('無法更改狀態，請連繫服務人員')

        return redirect(request.url)
    # 4. HANDLE GET (The View)
    introduction_link = get_introduction_link(matching.object)
    msg = f"""{name}的<a href='{introduction_link}'>介紹卡</a>，你們的匹配分數：{matching.grading_metric}"""
    return render_template('confirm.html',
                           header='赴約意願確認',
                           message=msg,
                           matching=matching
                           )


@bp.route('/liked/<token>', methods=['GET', 'POST'])
@match_transaction
def liked(matching):

    # Get the name using the ID derived from the token
    name = get_proper_name(matching.object.name, matching.object.gender)

    # 3. HANDLE POST (The Action)
    if request.method == 'POST':
        change_state('liked_waiting', 'rest_r1_sending', matching)
        return render_template('thank_you.html',
                               header="✅您已確認相遇",
                               message="""
                            屬於你們的連結已悄然展開 < br > 我們將安排接下來的約會流程 < br > 讓浪漫的相遇在每個細節中綻放
                            """)

    return render_template('confirm.html',
                           message=f"""{name}有意願認識您 < br > 你們的匹配程度有{matching.obj_grading_metric}分！ < br > 是否要交個朋友呢？""",
                           header='邀請回覆',
                           btn_name='可以',
                           action_url=url_for('liked'))

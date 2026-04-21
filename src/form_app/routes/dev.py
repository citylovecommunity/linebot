from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user

from form_app.decorators import developer_required

bp = Blueprint('dev_bp', __name__, url_prefix='/dev')


def _fake_member(id, name, gender):
    surname = '先生' if gender == 'M' else '小姐'
    return SimpleNamespace(
        id=id,
        name=name,
        gender=gender,
        proper_name=name[0] + surname,
        introduction_link='#',
    )


def _fake_message(id, sender, content, minutes_ago, is_system=False):
    return SimpleNamespace(
        id=id,
        user=sender,
        content=content,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        is_system_notification=is_system,
    )


def _fake_proposal(matching_id, proposer_id, partner_id, confirmed=False):
    return SimpleNamespace(
        id=1,
        matching_id=matching_id,
        proposer_id=proposer_id,
        restaurant_name='饗食天堂 北車店',
        proposed_datetime=datetime.now(timezone.utc) + timedelta(days=5),
        who_reservation=proposer_id,
        is_pending=not confirmed,
        is_confirmed=confirmed,
        is_cancelled=False,
    )


def _fake_matching(id, partner, score, status_value, last_msg_content=None, last_msg_mine=True, days_ago=3):
    from form_app.models import MatchingStatus
    status_map = {
        'ACTIVE': (True, False, False, False),
        'COMPLETED': (False, False, True, False),
        'CANCELLED': (False, False, False, True),
    }
    is_active, _, is_completed, is_cancelled = status_map.get(status_value, (True, False, False, False))

    last_message = None
    if last_msg_content:
        sender_id = current_user.id if last_msg_mine else partner.id
        last_message = SimpleNamespace(
            content=last_msg_content,
            user_id=sender_id,
        )

    def get_grading(_user_id):
        return score

    def get_partner(_user_id):
        return partner

    return SimpleNamespace(
        id=id,
        cool_name=f'預覽配對{id:02d}',
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        status=SimpleNamespace(value=status_value),
        is_pending=False,
        is_active=is_active,
        is_completed=is_completed,
        is_cancelled=is_cancelled,
        last_message=last_message,
        last_message_id=id if last_msg_content else None,
        get_grading=get_grading,
        get_partner=get_partner,
    )


@bp.route('/dashboard-preview')
@login_required
@developer_required
def dashboard_preview():
    partners = [
        _fake_member(10, '林小華', 'F'),
        _fake_member(11, '王美玲', 'F'),
        _fake_member(12, '陳雅婷', 'F'),
        _fake_member(13, '張怡君', 'F'),
        _fake_member(14, '李佳穎', 'F'),
    ]

    fake_matches = [
        _fake_matching(1, partners[0], score=82, status_value='ACTIVE',
                       last_msg_content='好的，我很期待！😊', last_msg_mine=False, days_ago=0),
        _fake_matching(2, partners[1], score=61, status_value='ACTIVE',
                       last_msg_content='你覺得哪裡好吃呢？', last_msg_mine=True, days_ago=1),
        _fake_matching(3, partners[2], score=28, status_value='ACTIVE',
                       last_msg_content=None, days_ago=2),
        _fake_matching(4, partners[3], score=75, status_value='COMPLETED',
                       last_msg_content='謝謝這段時間 🙏', last_msg_mine=False, days_ago=14),
        _fake_matching(5, partners[4], score=44, status_value='CANCELLED',
                       last_msg_content='抱歉，我想先暫停配對', last_msg_mine=True, days_ago=7),
    ]

    return render_template(
        'dashboard.html',
        current_user=current_user,
        missing_items=[],
        preview_matches=fake_matches,
        preview_banner=True,
    )


@bp.route('/chat-preview')
@login_required
@developer_required
def chat_preview():
    # step: 1=matched, 2=pending proposal, 3=confirmed, 4=cancelled
    step = request.args.get('step', 1, type=int)

    me = _fake_member(1, '陳大明', 'M')
    partner = _fake_member(2, '林小華', 'F')

    # Patch current_user.id so is_me logic works correctly in the template
    me.id = current_user.id

    base_messages = [
        _fake_message(1, partner, '你好！很高興認識你 😊', 60),
        _fake_message(2, me,      '你好！我也很開心能配對到你', 55),
        _fake_message(3, partner, '你平常喜歡做什麼呢？', 50),
        _fake_message(4, me,      '我喜歡爬山和看電影，你呢？', 45),
        _fake_message(5, partner, '我喜歡料理和瑜珈！', 40),
        _fake_message(6, me,      '哇！那我們可以一起做很多事情耶 😄', 30),
    ]

    proposal = None
    status_step = step

    if step == 2:
        proposal = _fake_proposal(0, partner.id, me.id, confirmed=False)
        base_messages.append(
            _fake_message(7, partner, '我想約你出去吃飯，你有空嗎？', 10)
        )
    elif step == 3:
        proposal = _fake_proposal(0, partner.id, me.id, confirmed=True)
        base_messages.append(
            _fake_message(8, me, '✅ 接受在饗食天堂的約會提議！', 5, is_system=True)
        )
    elif step == 4:
        base_messages.append(
            _fake_message(9, me, '已取消配對', 2, is_system=True)
        )

    matching = SimpleNamespace(
        id=0,
        cool_name='預覽配對',
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
        status=SimpleNamespace(value='CANCELLED' if step == 4 else 'ACTIVE'),
        is_cancelled=(step == 4),
        cancel_by_id=me.id if step == 4 else None,
        messages=base_messages,
        ui_proposal=proposal,
    )

    return render_template(
        'matching_dashboard.html',
        matching=matching,
        partner=partner,
        messages=base_messages,
        proposal=proposal,
        status_step=status_step,
        is_preview=True,
        is_dev=False,
    )

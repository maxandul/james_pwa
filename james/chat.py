from uuid import uuid4

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select

from .extensions import db
from .jayjay import configured, run_turn, start_turn
from .models import ChatTurn
from .services import Conflict
from .views import household_required

chat = Blueprint('chat', __name__)


@chat.route('/jayjay', methods=['GET', 'POST'])
@household_required
def index():
    error, status = None, 200
    if request.method == 'POST':
        if not configured():
            return render_template('error.html', message='JayJay ist noch nicht mit OpenAI verbunden.'), 503
        try:
            turn, created = start_turn(current_user.id, g.household.id,
                request.form.get('message'), request.form.get('request_id'))
            if created:
                run_turn(turn.id, current_user.id, g.household.id)
            return redirect(url_for('chat.index', turn=turn.id))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    turns = db.session.scalars(select(ChatTurn).where(ChatTurn.user_id == current_user.id,
        ChatTurn.household_id == g.household.id).order_by(ChatTurn.id.desc()).limit(12)).all()
    return render_template('chat.html', ready=configured(), turns=list(reversed(turns)),
        error=error, chat_request_id=str(uuid4())), status

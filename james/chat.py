from uuid import UUID, uuid4

from flask import Blueprint, abort, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import delete, func, select

from .assortment import lock_household
from .extensions import db
from .jayjay import configured, run_turn, start_turn
from .models import ChatConversation, ChatTurn
from .pwa import owner_key
from .services import Conflict, clean_text
from .views import household_required

chat = Blueprint('chat', __name__)


def conversations():
    return select(ChatConversation).where(ChatConversation.user_id == current_user.id,
        ChatConversation.household_id == g.household.id)


def private_conversation(identifier):
    try:
        identifier = str(UUID(identifier))
    except (ValueError, TypeError, AttributeError):
        abort(404)
    conversation = db.session.scalar(conversations().where(ChatConversation.id == identifier))
    if not conversation:
        abort(404)
    return conversation


@chat.route('/jayjay', methods=['GET', 'POST'])
@household_required
def index():
    error, status, changed = None, 200, False
    panel = request.args.get('panel') == '1'
    conversation = None
    identifier = request.form.get('conversation_id') if request.method == 'POST' else request.args.get('conversation')
    if request.method == 'GET' and identifier:
        conversation = private_conversation(identifier)
    elif request.method == 'GET' and request.args.get('new') != '1':
        conversation = db.session.scalar(conversations().order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc()).limit(1))
    identifier = identifier or (conversation.id if conversation else str(uuid4()))
    if request.method == 'POST':
        # Older clients without conversation fields retain the previous replay contract.
        operation = request.form.get('operation', 'message')
        try:
            if operation in ('rename', 'delete'):
                lock_household(g.household.id)
                conversation = private_conversation(identifier)
                if operation == 'rename':
                    conversation.title = clean_text(request.form.get('title'), 'Titel', 100)
                else:
                    running = db.session.scalar(select(ChatTurn.id).where(ChatTurn.conversation_id == identifier,
                        ChatTurn.state == 'running').limit(1))
                    if running:
                        raise Conflict('Ein noch nicht bestätigter Auftrag kann nicht gelöscht werden. Bitte zuerst den Verlauf prüfen.')
                    db.session.execute(delete(ChatTurn).where(ChatTurn.conversation_id == identifier,
                        ChatTurn.user_id == current_user.id, ChatTurn.household_id == g.household.id))
                    db.session.delete(conversation)
                    conversation = None
                db.session.commit()
                if operation == 'delete':
                    identifier = str(uuid4())
            elif operation == 'message':
                if not configured():
                    raise ValueError('JayJay ist noch nicht mit OpenAI verbunden.')
                # No-field legacy POSTs use the old null conversation for idempotent retries.
                turn, created = start_turn(current_user.id, g.household.id,
                    request.form.get('message'), request.form.get('request_id'), request.form.get('conversation_id'))
                if created:
                    run_turn(turn.id, current_user.id, g.household.id)
                identifier = turn.conversation_id
                conversation = private_conversation(identifier) if identifier else None
                changed = bool(turn.actions)
            else:
                raise ValueError('Unbekannte Chat-Aktion.')
            if not panel:
                return redirect(url_for('chat.index', conversation=identifier) if identifier else url_for('chat.index'))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else (503 if not configured() and operation == 'message' else 400)
            if request.form.get('conversation_id'):
                conversation = db.session.scalar(conversations().where(ChatConversation.id == identifier))
    turn_query = select(ChatTurn).where(ChatTurn.user_id == current_user.id,
        ChatTurn.household_id == g.household.id, ChatTurn.conversation_id == (conversation.id if conversation else None))
    # A new draft must not display the ungrouped legacy conversation.
    if request.method == 'GET' and request.args.get('new') == '1':
        turn_query = turn_query.where(False)
    page = max(1, min(request.args.get('page', 1, type=int), 100000))
    total = db.session.scalar(select(func.count()).select_from(turn_query.subquery()))
    page = min(page, max(1, (total + 29) // 30))
    turns = db.session.scalars(turn_query.order_by(ChatTurn.id.desc()).offset((page - 1) * 30).limit(30)).all()
    search = request.args.get('q', '').strip()[:100]
    history_query = conversations()
    if search:
        history_query = history_query.where(ChatConversation.title.ilike('%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%', escape='\\'))
    history_page = max(1, request.args.get('history_page', 1, type=int))
    history = db.session.scalars(history_query.order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc())
        .offset((history_page - 1) * 30).limit(31)).all()
    context = dict(ready=configured(), turns=list(reversed(turns)), conversation=conversation,
        conversation_id=identifier or '', history=history[:30], history_more=len(history) > 30,
        history_page=history_page, search=search, history_open=request.args.get('history') == '1',
        page=page, older=page * 30 < total,
        error=error, chat_request_id=str(uuid4()), panel=panel, draft=request.form.get('message', '') if error else '')
    if panel:
        response = jsonify(html=render_template('_chat_body.html', **context), owner=owner_key(g.membership),
            conversation_id=identifier, saved=bool(conversation),
            active_url=url_for('chat.index', panel='1', conversation=conversation.id if conversation else None,
                new='1' if not conversation and not turns else None), changed=changed)
        response.headers['Cache-Control'] = 'no-store'
        return response, status
    return render_template('chat.html', **context), status

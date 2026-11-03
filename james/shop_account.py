"""Conservative credential mapping for one deployment-bound household account.

Values are used only in authentication control events, never agent prompts.
Unknown fields/methods (including MFA) remain a manual PWA challenge.
"""
from werkzeug.exceptions import HTTPException

from .shop_login import SHOP_LOGIN_ORIGINS, fields_for


_EMAIL_LABELS = {'email', 'e-mail', 'e-mail-adresse', 'email address', 'e-mail address', 'benutzername', 'username'}
_PASSWORD_LABELS = {'password', 'passwort'}


def credential_response(schema, config, used_roles):
    if schema.get('credential_origin') not in SHOP_LOGIN_ORIGINS:
        return None
    email, password = config.get('GALAXUS_EMAIL', ''), config.get('GALAXUS_PASSWORD', '')
    if not email or not password or len(email) > 2048 or len(password) > 2048:
        return None
    options = schema.get('options', [])
    if not isinstance(options, list) or len(options) > 12:
        return None
    candidates = []
    for selected in ([o.get('id') for o in options if isinstance(o, dict)] if options else [None]):
        try:
            fields = fields_for(schema, selected)
        except HTTPException:
            continue
        roles, values = set(), []
        for field in fields:
            label = field['label'].strip().casefold()
            kind = field.get('type')
            if kind == 'email' and label in _EMAIL_LABELS:
                role, value = 'email', email
            elif kind == 'text' and label in _EMAIL_LABELS:
                role, value = 'email', email
            elif kind == 'password' and label in _PASSWORD_LABELS:
                role, value = 'password', password
            else:
                break  # Never fill codes, consent controls, or unidentified fields.
            if role in roles:
                break
            roles.add(role)
            values.append({'field_id': field['id'], 'value': value})
        else:
            # A new password step may repeat the email field. Allow that one
            # transition, but never replay a password or an email-only step.
            fresh = roles - used_roles
            repeated = roles & used_roles
            if values and fresh and (not repeated or
                    (repeated == {'email'} and fresh == {'password'})):
                response = {'type': 'browser_authentication', 'action': 'submit', 'fields': values}
                if selected is not None:
                    response['selected_option'] = selected
                candidates.append((response, roles))
    # An ambiguous method choice must be made by the user, not by a guess.
    return candidates[0] if len(candidates) == 1 else None


def manual_reason(schema, config, used_roles):
    """Fixed diagnostic categories only; never return field labels or values."""
    if schema.get('options'):
        return 'manual_method'
    if credential_response(schema, config, set()) and used_roles:
        return 'manual_repeat'
    return 'manual_fields'

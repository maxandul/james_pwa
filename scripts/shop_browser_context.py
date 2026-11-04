"""Operator-only persistence proof; no model, cart mutation, or checkout.

State contains provider references, never cookies/passwords/live URLs. Do not expose
this CLI as a web route: PWA ownership and mobile controls are a separate phase.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import UUID


class BrowserUnavailable(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def identifier(value):
    return str(UUID(value))


class Browserbase:
    def __init__(self, key, project):
        if not key or not project:
            raise BrowserUnavailable('BROWSERBASE_API_KEY und BROWSERBASE_PROJECT_ID fehlen.')
        self.key, self.project = key, identifier(project)

    def request(self, method, path, payload=None):
        req = Request('https://api.browserbase.com/v1/' + path, method=method,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'X-BB-API-Key': self.key, 'Content-Type': 'application/json'})
        try:
            with build_opener(NoRedirect).open(req, timeout=20) as response:
                raw = response.read(256001)
            if len(raw) > 256000:
                raise ValueError()
            return json.loads(raw) if raw else {}
        except HTTPError as exc:
            raise BrowserUnavailable(f'Browserdienst nicht verfügbar (HTTP {exc.code}).', status=exc.code) from None
        except Exception:
            raise BrowserUnavailable('Browserdienst nicht erreichbar; Ausgang der Anfrage prüfen.') from None

    def create_context(self):
        return identifier(self.request('POST', 'contexts', {'projectId': self.project})['id'])

    def create_session(self, context, *, keep_alive=True):
        return self.request('POST', 'sessions', {
            'projectId': self.project, 'region': 'eu-central-1',
            'timeout': 720, 'keepAlive': keep_alive,
            'browserSettings': {'context': {'id': identifier(context), 'persist': True},
                                'recordSession': False, 'logSession': False,
                                'solveCaptchas': False, 'advancedStealth': False,
                                'viewport': {'width': 1024, 'height': 768}}})

    def session(self, sid):
        return self.request('GET', 'sessions/' + identifier(sid))

    def release(self, sid):
        return self.request('POST', 'sessions/' + identifier(sid),
                            {'projectId': self.project, 'status': 'REQUEST_RELEASE'})

    def live_url(self, sid):
        data = self.request('GET', 'sessions/' + identifier(sid) + '/debug')
        url = data['debuggerFullscreenUrl']
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != 'www.browserbase.com'
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise BrowserUnavailable('Unerwartete Browseransicht; nicht öffnen.')
        return url

    def delete_context(self, context):
        self.request('DELETE', 'contexts/' + identifier(context))


class State:
    def __init__(self, path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        temporary = self.path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            os.chmod(temporary, 0o600)
            json.dump(self.data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)


@contextmanager
def locked_state(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BrowserUnavailable('Dieser Shop-Browser wird bereits bearbeitet.') from None
        if path.is_symlink():
            raise BrowserUnavailable('Statusdatei darf keine Verknüpfung sein.')
        yield State(path)


def open_galaxus(connect_url):
    # No raw Playwright error escapes: it may contain a credential-bearing CDP URL.
    try:
        from playwright.sync_api import sync_playwright
        parsed = urlsplit(connect_url)
        if parsed.scheme != 'wss' or not (parsed.hostname == 'connect.browserbase.com'
                or (parsed.hostname or '').endswith('.browserbase.com')):
            raise ValueError()
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(connect_url, timeout=20000)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            page.goto('https://www.galaxus.ch/', wait_until='domcontentloaded', timeout=30000)
            # Disconnect the client; keepAlive retains the provider session for the user.
    except Exception:
        raise BrowserUnavailable('Browserstart fehlgeschlagen. Sitzung schliessen und Status prüfen.') from None


def close_session(provider, state, *, sleep=time.sleep):
    sid = state.data.get('session_id')
    if not sid:
        return
    provider.release(sid)
    for _ in range(10):
        status = provider.session(sid)['status']
        if status in ('COMPLETED', 'TIMED_OUT', 'ERROR'):
            # Provider documents a synchronization delay before reusing a context.
            sleep(5)
            state.data.pop('session_id', None)
            state.data['last_session_status'] = status
            state.save()
            return
        sleep(1)
    raise BrowserUnavailable('Sitzung wird noch geschlossen. Schliessen später erneut ausführen.')


def execute(action, provider, state, *, navigate=open_galaxus):
    if state.data.get('project_id') not in (None, provider.project):
        raise BrowserUnavailable('Statusdatei gehört zu einem anderen Browserprojekt.')
    if state.data.get('creation_pending'):
        raise BrowserUnavailable('Ausgang einer Erstellung unklar. Im Browserbase-Dashboard abgleichen; keine Wiederholung.')
    if action == 'init':
        if state.data:
            raise BrowserUnavailable('Profil besteht bereits. Öffnen statt neu erstellen.')
        state.data = {'project_id': provider.project, 'creation_pending': 'context'}
        state.save()
        context = provider.create_context()
        state.data = {'project_id': provider.project, 'context_id': context}
        state.save()
        return 'Browserprofil angelegt. Anmeldung ist noch nicht geprüft.'
    if not state.data.get('context_id'):
        raise BrowserUnavailable('Zuerst das Browserprofil anlegen.')
    if action == 'close':
        close_session(provider, state)
        return 'Browsersitzung geschlossen. Anmeldung bleibt im Profil, soweit der Shop dies erlaubt.'
    if action == 'forget':
        close_session(provider, state)
        provider.delete_context(state.data['context_id'])
        state.data = {}
        state.save()
        return 'Gespeichertes Browserprofil gelöscht.'
    if action == 'open':
        if state.data.get('session_id'):
            raise BrowserUnavailable('Eine Sitzung ist noch registriert. Erst schliessen; keine parallelen Sitzungen.')
        state.data['creation_pending'] = 'session'
        state.save()
        session = provider.create_session(state.data['context_id'])
        state.data['session_id'] = identifier(session['id'])
        state.data.pop('creation_pending')
        state.save()
        try:
            navigate(session['connectUrl'])
            return provider.live_url(state.data['session_id'])
        except Exception:
            # Keep the reference if release fails, so an operator can retry cleanup.
            close_session(provider, state)
            raise BrowserUnavailable('Browseransicht nicht verfügbar. Es wurde kein Login bestätigt.') from None
    raise BrowserUnavailable('Unbekannte Aktion.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'open', 'close', 'forget'))
    parser.add_argument('--state', type=Path, required=True,
                        help='Private Statusdatei ausserhalb des Repositorys; ein Profil pro Haushalt.')
    args = parser.parse_args()
    try:
        provider = Browserbase(os.getenv('BROWSERBASE_API_KEY'), os.getenv('BROWSERBASE_PROJECT_ID'))
        with locked_state(args.state) as state:
            message = execute(args.action, provider, state)
        print(message)  # open prints a temporary control URL: private terminal only, never CI/logs.
    except (BrowserUnavailable, ValueError, KeyError, OSError):
        # CLI diagnostics are deliberately fixed: underlying errors may contain secrets.
        parser.exit(1, 'Shop-Browser konnte die Aktion nicht abschliessen. Konfiguration und private Statusdatei prüfen; bei creation_pending zuerst im Dashboard abgleichen.\n')


if __name__ == '__main__':
    main()

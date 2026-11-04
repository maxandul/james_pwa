from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from james.shop_cart_agent import CartDriver, safe_link


@pytest.mark.parametrize('url', ['https://www.galaxus.ch/de/cart',
    'https://www.galaxus.ch/de/s2/product/bluu-universal-14684120'])
def test_read_navigation(url):
    assert safe_link(url)


@pytest.mark.parametrize('url', ['https://evil.test/de/cart',
    'https://www.galaxus.ch.evil.test/de/cart', 'https://www.galaxus.ch/de/checkout',
    'https://www.galaxus.ch/de/account/settings',
    'https://www.galaxus.ch/de/s2/product/other-999',
    'https://user:pass@www.galaxus.ch/de/cart'])
def test_other_destinations_blocked(url):
    assert not safe_link(url)


def driver():
    page = Mock()
    page.url = 'https://www.galaxus.ch/de/s2/product/bluu-universal-14684120'
    return CartDriver(page, lambda: False, Mock())


def test_no_checkout_or_quantity_edit():
    d = driver()
    for label in ['Zur Kasse', 'Jetzt bestellen', 'Kaufen', 'Entfernen', '+']:
        assert not d.permitted({'tag': 'BUTTON', 'label': label})
    assert not d.permitted({'tag': 'BUTTON', 'label': 'In den Warenkorb', 'product': '999'})


def test_ambiguous_add_consumes_budget_before_dispatch():
    d = driver()
    d.page.evaluate.return_value = {'tag': 'BUTTON', 'label': 'In den Warenkorb'}
    d.page.mouse.click.side_effect = TimeoutError('synthetic')
    action = SimpleNamespace(button='left', keys=[], x=5, y=5)
    for _ in range(2):
        with pytest.raises(TimeoutError):
            d.click(action)
    with pytest.raises(RuntimeError, match='control_not_allowed'):
        d.click(action)
    assert d.page.mouse.click.call_count == 2


def test_cancellation_blocks_every_action():
    d = driver()
    d.stopped = lambda: True
    with pytest.raises(RuntimeError, match='cancelled'):
        d.screenshot()
    d.page.screenshot.assert_not_called()


@pytest.mark.parametrize('label', ['4 items in cart', 'Warenkorb ist leer', '2 Produkte im Warenkorb'])
def test_cart_header_is_bound_by_id_not_count_or_language(label):
    d = driver()
    c = {'tag': 'BUTTON', 'id': 'toggleShoppingCartButton', 'label': label}
    assert d.permitted(c)
    assert not d.permitted({**c, 'id': 'otherButton'})
    assert not d.permitted({**c, 'href': 'https://www.galaxus.ch/en/checkout'})


def test_english_navigation_remains_bounded():
    assert safe_link('https://www.galaxus.ch/en/cart')
    assert safe_link('https://www.galaxus.ch/en/search?q=14684120')
    for url in ('https://www.galaxus.ch/en/checkout',
                'https://www.galaxus.ch/en/account/settings',
                'https://www.galaxus.ch/en/s7/product/other-999'):
        assert not safe_link(url)


def test_english_add_has_same_product_and_quantity_limits():
    d = driver()
    c = {'tag': 'BUTTON', 'label': 'Add to cart', 'product': '14684120'}
    assert d.permitted(c)
    assert not d.permitted({**c, 'product': '999'})
    d.additions['14684120'] = 2
    assert not d.permitted(c)


def test_blocked_navigation_has_fixed_diagnostic_without_private_text():
    d = driver()
    d.page.evaluate.return_value = {'tag': 'A', 'href': 'https://www.galaxus.ch/en/account/settings',
                                    'label': 'Synthetic private account name'}
    with pytest.raises(RuntimeError):
        d.click(SimpleNamespace(button='left', keys=[], x=5, y=5))
    assert d.blocked_code == 'CONTROL_LINK'
    d.page.mouse.click.assert_not_called()


def test_address_bar_shortcut_is_reported_without_dispatch():
    d = driver()
    d.page.evaluate.return_value = {'tag': 'BODY'}
    with pytest.raises(RuntimeError):
        d.keypress(SimpleNamespace(keys=['CTRL', 'L']))
    assert d.blocked_code == 'CONTROL_KEY'
    d.page.keyboard.press.assert_not_called()

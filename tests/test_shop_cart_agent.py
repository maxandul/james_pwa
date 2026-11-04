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

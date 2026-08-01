from opportunity_engine.discovery.auksjonen_playwright_fallback import (
    AuksjonenPlaywrightFallbackVerifier,
)
from opportunity_engine.discovery.clothing_inventory_search import PageVerification


class _FakeButton:
    def __init__(self, *, visible: bool = True, click_error: Exception | None = None):
        self.first = self
        self._visible = visible
        self._click_error = click_error
        self.clicked = False

    def count(self):
        return 1

    def is_visible(self):
        return self._visible

    def click(self, *, timeout):
        assert timeout == 3000
        if self._click_error:
            raise self._click_error
        self.clicked = True


class _MissingButton:
    first = None

    def count(self):
        return 0


class _FakePage:
    def __init__(self, buttons):
        self._buttons = list(buttons)
        self.waits = []

    def get_by_role(self, role, *, name):
        assert role == "button"
        return self._buttons.pop(0) if self._buttons else _MissingButton()

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)


class _NavigationPage(_FakePage):
    def __init__(self, buttons):
        super().__init__(buttons)
        self.url = "https://auksjonen.no/auksjon/overskuddsvarer/test/557914"
        self.calls = []

    def goto(self, url, *, wait_until):
        self.calls.append(("goto", url, wait_until))

    def wait_for_load_state(self, state):
        self.calls.append(("wait_for_load_state", state))

    def content(self):
        self.calls.append(("content",))
        return "<html><body>item content</body></html>"


def _unresolved(url):
    return PageVerification(url=url, verified=False, error="insufficient public listing content")


def test_visible_tillat_alle_button_is_clicked_once():
    button = _FakeButton()
    verifier = AuksjonenPlaywrightFallbackVerifier(_unresolved)
    verifier._page = _FakePage([button])

    dismissed = verifier._dismiss_cookie_consent()

    assert dismissed is True
    assert button.clicked is True
    assert verifier._page.waits == [500]


def test_missing_or_broken_consent_button_fails_open_to_normal_verification():
    verifier = AuksjonenPlaywrightFallbackVerifier(_unresolved)
    verifier._page = _FakePage([
        _MissingButton(),
        _FakeButton(click_error=RuntimeError("detached")),
        _MissingButton(),
    ])

    assert verifier._dismiss_cookie_consent() is False


def test_rendered_page_waits_again_after_cookie_consent():
    button = _FakeButton()
    page = _NavigationPage([button])
    verifier = AuksjonenPlaywrightFallbackVerifier(_unresolved)
    verifier._page = page

    final_url, html = verifier._load_rendered_page(page.url)

    assert final_url == page.url
    assert html == "<html><body>item content</body></html>"
    assert button.clicked is True
    assert page.waits == [2500.0, 500, 2500.0]
    assert ("wait_for_load_state", "domcontentloaded") in page.calls

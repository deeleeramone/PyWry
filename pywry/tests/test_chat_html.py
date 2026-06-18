"""Tests for pywry.chat.html."""

from __future__ import annotations

import pytest

from pywry.chat.html import build_chat_html


class TestBuildChatHtml:
    def test_returns_string(self):
        html = build_chat_html()
        assert isinstance(html, str)
        assert html.startswith('<div class="pywry-chat"')

    def test_includes_message_area(self):
        html = build_chat_html()
        assert 'id="pywry-chat-messages"' in html

    def test_input_textarea_present(self):
        html = build_chat_html()
        assert 'id="pywry-chat-input"' in html

    def test_send_button_present(self):
        html = build_chat_html()
        assert 'id="pywry-chat-send"' in html

    def test_sidebar_default_present(self):
        html = build_chat_html()
        assert 'id="pywry-chat-conv-btn"' in html

    def test_sidebar_disabled(self):
        html = build_chat_html(show_sidebar=False)
        assert "pywry-chat-conv-btn" not in html

    def test_settings_default_present(self):
        html = build_chat_html()
        assert 'id="pywry-chat-settings-toggle"' in html

    def test_settings_disabled(self):
        html = build_chat_html(show_settings=False)
        assert "pywry-chat-settings-toggle" not in html

    def test_context_disabled_by_default(self):
        html = build_chat_html()
        assert "pywry-chat-mention-popup" not in html

    def test_context_enabled(self):
        html = build_chat_html(enable_context=True)
        assert 'id="pywry-chat-mention-popup"' in html

    def test_attach_disabled_by_default(self):
        html = build_chat_html()
        assert "pywry-chat-attach-btn" not in html
        assert "pywry-chat-drop-overlay" not in html

    def test_attach_enabled(self):
        html = build_chat_html(enable_file_attach=True)
        assert 'id="pywry-chat-attach-btn"' in html
        assert 'id="pywry-chat-drop-overlay"' in html

    def test_file_accept_types(self):
        html = build_chat_html(enable_file_attach=True, file_accept_types=[".csv", ".json"])
        assert ".csv" in html
        assert ".json" in html
        assert "data-accept-types" in html

    def test_file_accept_types_ignored_without_attach(self):
        html = build_chat_html(enable_file_attach=False, file_accept_types=[".csv"])
        assert "data-accept-types" not in html

    def test_container_id(self):
        html = build_chat_html(container_id="my-chat")
        assert 'id="my-chat"' in html

    def test_no_container_id(self):
        html = build_chat_html()
        # Container element should not have id attribute
        assert html.startswith('<div class="pywry-chat"')
        # The next attribute we expect is data-* if attachments enabled, else just close >
        # Make sure no leading id="" injected
        assert 'id=""' not in html

    def test_header_actions_injected(self):
        html = build_chat_html(header_actions="<button>Custom</button>")
        assert "<button>Custom</button>" in html

    def test_typing_indicator(self):
        html = build_chat_html()
        assert 'id="pywry-chat-typing"' in html

    def test_new_msg_badge(self):
        html = build_chat_html()
        assert 'id="pywry-chat-new-msg-badge"' in html

    def test_todo_panel(self):
        html = build_chat_html()
        assert 'id="pywry-chat-todo"' in html

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"show_sidebar": False, "show_settings": False},
            {"enable_context": True, "enable_file_attach": True},
            {"show_sidebar": True, "show_settings": True, "enable_context": True},
        ],
    )
    def test_combinations_render(self, kwargs):
        # Smoke test for combos
        html = build_chat_html(**kwargs)
        assert html.startswith('<div class="pywry-chat"')
        assert html.endswith("</div>")

import unittest
from pathlib import Path

import server


class ChatAssistantTests(unittest.TestCase):
    def test_service_reply_is_helpful(self):
        result = server.build_chat_response("I need roofing for a house")
        self.assertIn("roof", result["reply"].lower())
        self.assertFalse(result["handoff"])

    def test_quote_request_triggers_whatsapp_handoff(self):
        result = server.build_chat_response("Please quote my house in Durban. My name is Thabo. Call me on 0821234567")
        self.assertTrue(result["handoff"])
        self.assertIn("wa.me", result["whatsappUrl"])

    def test_homepage_contains_chat_widget(self):
        html = Path("index.html").read_text(encoding="utf-8")
        self.assertIn("chat-toggle", html)
        self.assertIn("chat-widget", html)


if __name__ == "__main__":
    unittest.main()

import unittest
from start_handler import start_reply


class StartTests(unittest.TestCase):
    def test_private_start_opens_mini_app(self):
        for command in ('/start', '/start campaign', '/start@RTPZSBOT'):
            reply = start_reply({'chat': {'type': 'private', 'id': 123}, 'text': command})
            button = reply['reply_markup']['keyboard'][2][0]
            self.assertEqual(reply['chat_id'], 123)
            self.assertEqual(button['text'], '📱 打开数据站')
            self.assertTrue(button['web_app']['url'].startswith('https://'))

    def test_does_not_reply_to_other_messages_or_groups(self):
        for kind, text in [('group', '/start'), ('private', '你好'), ('private', '/starter'), ('private', '/start@OtherBot')]:
            self.assertIsNone(start_reply({'chat': {'type': kind, 'id': 123}, 'text': text}))

import unittest
import bot


class RTPTests(unittest.TestCase):
    def test_percentage(self):
        self.assertEqual(bot.pct(0.965), "96.50%")

    def test_wrong_window(self):
        row = {
            "scope": "slot",
            "window": "24h",
            "game": {
                "kind": "slots",
                "slug": "sample-slot"
            },
            "rtp": 0.965,
            "n": 100,
            "wagered_usd": 100
        }
        with self.assertRaises(bot.BotError):
            bot.parse_rows({"rows": [row]}, "10m")

    def test_invalid_response(self):
        with self.assertRaises(bot.BotError):
            bot.parse_rows({}, "10m")


if __name__ == "__main__":
    unittest.main()

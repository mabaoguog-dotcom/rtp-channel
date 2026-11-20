import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import bot
import chat_queries as chat


class ChatQueriesTests(unittest.TestCase):
    def test_all_verified_names_and_script_variants_are_searchable(self):
        catalog={g['slug']:g for g in chat.catalog()}
        for slug, record in chat.names().items():
            with self.subTest(slug=slug):
                self.assertIn(slug,catalog)
                game=catalog[slug]
                self.assertIsNotNone(bot.chinese_name(game))
                self.assertTrue(record['source'].startswith('https://'))
                self.assertTrue(chat.matches(game,record['zh']))
                for alias in record.get('aliases',[]):self.assertTrue(chat.matches(game,alias))

    def test_versions_and_providers_do_not_inherit_other_names(self):
        game=next(g for g in chat.catalog() if g['slug']=='sweet-bonanza-2500')
        self.assertTrue(chat.matches(game,'甜入心扉 2500'))
        self.assertFalse(chat.matches(game,'甜入心扉1000'))
        wrong=copy.deepcopy(game);wrong['provider']={'slug':'other-provider'}
        self.assertFalse(chat.matches(wrong,'甜入心扉'))

    @patch('chat_queries.game_rtp',return_value={})
    @patch('chat_queries.rows',return_value=[])
    def test_chinese_search_returns_verified_title_without_inventing_rtp(self, rows, detail):
        results=chat.search('甜入心扉2500')
        self.assertEqual(results[0][0],'sendMessage')
        self.assertIn('Sweet Bonanza 2500',results[0][1]['text'])
        self.assertIn('本次样本列表未包含',results[0][1]['text'])
        self.assertNotIn('0.00%',results[0][1]['text'])

    def test_period_selection_buttons_use_read_queries(self):
        method,payload=chat.query_replies('📊 实时RTP')[0]
        self.assertEqual(method,'sendMessage')
        self.assertEqual([b['text'] for b in payload['reply_markup']['keyboard'][0]],['10分钟RTP','1小时RTP','24小时RTP'])

    @patch('chat_queries.rows',return_value=[])
    def test_rtp_query_handles_empty_verified_sample(self, rows):
        method,payload=chat.query_replies('10分钟RTP')[0]
        self.assertEqual(method,'sendMessage')
        self.assertIn('暂无',payload['text'])

    @patch('chat_queries.bot.request_json',return_value={'bets':[]})
    def test_latest_big_win_handles_no_eligible_results(self, request):
        method,payload=chat.query_replies('💰 最新大额派彩')[0]
        self.assertEqual(method,'sendMessage')
        self.assertIn('暂无',payload['text'])

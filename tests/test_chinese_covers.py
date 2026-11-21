import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image

import game_poster

ROOT=Path(__file__).resolve().parents[1]


class ChineseCoverTests(unittest.TestCase):
    def test_native_cover_matches_exact_game_without_network(self):
        game=next(g for g in json.loads((ROOT/'game_catalog.json').read_text()) if g['slug']=='mahjong-ways-2')
        with patch('game_poster.urlopen',side_effect=AssertionError('Unexpected network request')):
            image=game_poster.cover(game)
        self.assertEqual(image.size,(288,288))
        self.assertEqual(image.mode,'RGB')

    def test_wrong_edition_or_provider_cannot_inherit_cover(self):
        game=next(g for g in json.loads((ROOT/'game_catalog.json').read_text()) if g['slug']=='mahjong-ways-2')
        game['thumb']=None
        for change in ('name','provider'):
            wrong=copy.deepcopy(game)
            if change=='name':wrong['name']='Mahjong Ways'
            else:wrong['provider']={'slug':'other-studio'}
            self.assertIsNone(game_poster.cover(wrong))

    def test_cover_manifest_preserves_original_source_and_image_integrity(self):
        manifest=json.loads((ROOT/'game-covers-zh/index.json').read_text())
        games={g['slug']:g for g in json.loads((ROOT/'game_catalog.json').read_text())}
        for slug, record in manifest.items():
            with self.subTest(slug=slug):
                game=games[slug]
                self.assertEqual(record['en'],game['name'])
                self.assertEqual(record['provider'],game['provider']['slug'])
                self.assertTrue(record['image_source'].startswith('https://public.pg-demo.com/'))
                self.assertIn('/zh/',record['image_source'])
                path=ROOT/'game-covers-zh'/record['file']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),record['sha256'])
                with Image.open(path) as image:
                    self.assertEqual(image.format,'PNG')
                    image.verify()

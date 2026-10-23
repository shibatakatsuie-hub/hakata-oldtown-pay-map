"""実行: python3 -B tests/test_geocode.py  （通信はしない。検索クエリの作り方と候補の選び方だけ確認）"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from common import normalize_address  # noqa: E402
from geocode import candidates, pick, ward_name  # noqa: E402


def feat(title, lon=130.40, lat=33.59):
    return {"properties": {"title": title}, "geometry": {"coordinates": [lon, lat]}}


class GeocodeTest(unittest.TestCase):
    def test_candidates_nakasu(self):
        self.assertEqual(candidates("福岡市博多区中洲1丁目8 清流公園内")[0], "福岡県福岡市博多区中洲1-8")
        self.assertEqual(candidates("福岡市博多区中洲3丁目7-10 若松ビル2F")[0], "福岡県福岡市博多区中洲3-7-10")
        self.assertEqual(
            candidates("福岡市中央区春吉1-7-18 武内ビル 1F"),
            ["福岡県福岡市中央区春吉1-7-18", "福岡県福岡市中央区春吉1-7", "福岡県福岡市中央区春吉1"],
        )

    def test_block_number_is_kept_after_normalizing(self):
        a = normalize_address("福岡市博多区上川端町4-235 2F")
        self.assertEqual(candidates(a)[0], "福岡県福岡市博多区上川端町4-235")

    def test_ward(self):
        self.assertEqual(ward_name("福岡県福岡市中央区春吉1-7"), "福岡市中央区")
        self.assertEqual(ward_name("福岡県福岡市博多区中洲1-8"), "福岡市博多区")

    def test_pick_requires_same_ward(self):
        q = "福岡県福岡市中央区春吉1-7-18"
        # 博多区の別の地名だけが返ってきた場合は採用しない
        self.assertIsNone(pick([feat("福岡県福岡市博多区春吉1-7")], q))
        got = pick([feat("福岡県福岡市博多区春吉1"), feat("福岡県福岡市中央区春吉1-7-18", 130.4, 33.58)], q)
        self.assertEqual(got["lat"], 33.58)

    def test_pick_hakata_still_works(self):
        q = "福岡県福岡市博多区上呉服町10-29"
        self.assertIsNotNone(pick([feat("福岡県福岡市博多区上呉服町10-29")], q))
        self.assertIsNone(pick([feat("福岡県福岡市東区箱崎10-29")], q))
        self.assertIsNone(pick([], q))


if __name__ == "__main__":
    unittest.main(verbosity=2)

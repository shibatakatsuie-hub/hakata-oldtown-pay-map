"""実行: python3 -B tests/test_hours_text.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from common import parse_hours  # noqa: E402
from hours_text import HoursTextError, convert  # noqa: E402


class ConvertTest(unittest.TestCase):
    def test_google_japanese_vertical(self):
        text = """月曜日
11:00～14:00, 17:00～22:00
火曜日
11:00～14:00, 17:00～22:00
水曜日
11:00～14:00, 17:00～22:00
木曜日
11:00～14:00, 17:00～22:00
金曜日
11:00～14:00, 17:00～22:00
土曜日
11:00～22:00
日曜日
定休日"""
        self.assertEqual(convert(text), "月-金 11:00-14:00,17:00-22:00; 土 11:00-22:00; 日 休")

    def test_one_line_and_fullwidth(self):
        self.assertEqual(
            convert("月曜日 １１：００～１４：００　火曜日 11:00〜14:00 水曜日 定休日"),
            "月・火 11:00-14:00; 水 休",
        )

    def test_everyday_and_24h(self):
        every = "\n".join(f"{d}曜日\n18:00～23:00" for d in "月火水木金土日")
        self.assertEqual(convert(every), "毎日 18:00-23:00")
        self.assertEqual(convert("月曜日 24 時間営業 火曜日 24 時間営業"), "月・火 00:00-24:00")

    def test_overnight(self):
        out = convert("金曜日 18:00～2:00 土曜日 18:00～翌2:00")
        self.assertEqual(out, "金・土 18:00-02:00")

    def test_holiday_parenthesis_and_days_not_given(self):
        # 『月曜日（祝日）』の注記は無視。書かれていない曜日は不明のまま
        out = convert("月曜日 (祝日) 11:00～15:00 水曜日 11:00～15:00")
        self.assertEqual(out, "月・水 11:00-15:00")
        week = parse_hours(out)
        self.assertIsNone(week[1])

    def test_noncontiguous_days_grouped(self):
        out = convert("月曜日 10:00～12:00 火曜日 休業 水曜日 10:00～12:00 木曜日 休業")
        self.assertEqual(out, "月・水 10:00-12:00; 火・木 休")

    def test_three_day_run(self):
        out = convert("月曜日 9:00～17:00 火曜日 9:00～17:00 水曜日 9:00～17:00")
        self.assertEqual(out, "月-水 09:00-17:00")

    def test_english_ampm(self):
        out = convert("Monday 11:00 AM – 2:00 PM, 5:00 – 10:00 PM\nTuesday Closed\nWednesday Open 24 hours")
        self.assertEqual(out, "月 11:00-14:00,17:00-22:00; 火 休; 水 00:00-24:00")
        self.assertEqual(convert("Friday 12:00 AM – 12:00 PM"), "金 00:00-12:00")

    def test_japanese_ampm(self):
        self.assertEqual(convert("月曜日 午前11:00～午後2:00"), "月 11:00-14:00")

    def test_output_is_always_readable_by_build_data(self):
        for text in ["月曜日 11:00～14:00, 17:00～22:00 火曜日 定休日", "土曜日 18:00～2:00"]:
            out = convert(text)
            self.assertTrue(parse_hours(out))

    def test_japanese_kanji_time_with_blank_lines_and_week_starting_thursday(self):
        # Googleマップの表示例: 曜日の順が木曜始まり・曜日の間に空行・『18時00分～22時00分』表記
        text = """木曜日
18時00分～22時00分

金曜日
18時00分～22時00分

土曜日
定休日

日曜日
定休日

月曜日
18時00分～22時00分

火曜日
18時00分～22時00分

水曜日
18時00分～22時00分"""
        self.assertEqual(convert(text), "月-金 18:00-22:00; 土・日 休")

    def test_kanji_time_variants(self):
        self.assertEqual(convert("月曜日 11時30分～14時"), "月 11:30-14:00")
        self.assertEqual(convert("月曜日 18時～翌2時30分"), "月 18:00-02:30")
        self.assertEqual(convert("月曜日 午前11時～午後2時半"), "月 11:00-14:30")
        self.assertEqual(convert("月曜日 24時間営業"), "月 00:00-24:00")  # 『24時間』は時刻と誤認しない

    def test_is_complete_week(self):
        from hours_text import is_complete_week
        seven = "\n".join(f"{d}曜日\n10:00～18:00" for d in "月火水木金土日")
        self.assertTrue(is_complete_week(seven))
        self.assertFalse(is_complete_week("\n".join(seven.split("\n")[:-1])))  # 日曜の時間がまだ
        self.assertFalse(is_complete_week("月曜日\n10:00～18:00"))
        self.assertFalse(is_complete_week(""))

    def test_errors(self):
        for bad, expect in [
            ("11:00～14:00", "曜日"),
            ("", "曜日"),
            ("月曜日 営業しています", "読み取れません"),
            ("月曜日 11:00～14:00 月曜日 12:00～15:00", "2回"),
        ]:
            with self.assertRaises(HoursTextError) as cm:
                convert(bad)
            self.assertIn(expect, str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

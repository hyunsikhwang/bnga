import unittest
from datetime import date

from benecafe_url import build_welfarecard_demand_url, subtract_one_month


class WelfarecardDemandUrlTest(unittest.TestCase):
    def test_requested_date_range_is_one_calendar_month(self):
        url = build_welfarecard_demand_url(date(2026, 8, 4))

        self.assertEqual(
            url,
            "https://rga.benecafe.co.kr/mywel/getWelfarecardDemandListVer"
            "?crdcoNo=HA&rtnTpCd=&crtcrdProdNo=&ecluCrtcrdRealHhAskYn=N"
            "&necluCrtcrdRealHhAskYn=N&searchStartDate=2026-07-04"
            "&searchEndDate=2026-08-04&applStatCd=00"
            "&alreadyApplicationExclustion=&multiCrtcrdRealYn=false&adminPswd=",
        )

    def test_previous_month_last_day_is_used_when_needed(self):
        self.assertEqual(subtract_one_month(date(2026, 3, 31)), date(2026, 2, 28))
        self.assertEqual(subtract_one_month(date(2024, 3, 31)), date(2024, 2, 29))

    def test_year_boundary_is_supported(self):
        self.assertEqual(subtract_one_month(date(2026, 1, 31)), date(2025, 12, 31))

    def test_requested_query_parameters_are_preserved(self):
        url = build_welfarecard_demand_url(date(2026, 8, 4))

        self.assertIn("crdcoNo=HA", url)
        self.assertIn("ecluCrtcrdRealHhAskYn=N", url)
        self.assertIn("necluCrtcrdRealHhAskYn=N", url)
        self.assertIn("applStatCd=00", url)
        self.assertIn("multiCrtcrdRealYn=false", url)


if __name__ == "__main__":
    unittest.main()

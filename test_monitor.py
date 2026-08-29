import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from benecafe_url import build_welfarecard_demand_url, subtract_one_month
import monitor


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


class CollectionFailureNotificationTest(unittest.TestCase):
    def test_missing_login_settings_are_reported_clearly(self):
        with patch.dict(
            "os.environ",
            {"BENECAFE_ID": "", "BENECAFE_PW": ""},
            clear=False,
        ):
            with self.assertRaisesRegex(
                monitor.BenecafeCollectionError,
                r"로그인 정보 미설정 \(BENECAFE_ID, BENECAFE_PW\)",
            ):
                monitor.run_benecafe(MagicMock())

    @patch("monitor.send_telegram")
    @patch("monitor.run_benecafe")
    @patch("monitor.sync_playwright")
    def test_collection_failure_reason_is_sent_to_bot(
        self,
        mock_sync_playwright,
        mock_run_benecafe,
        mock_send_telegram,
    ):
        mock_run_benecafe.side_effect = monitor.BenecafeCollectionError(
            "데이터 API 응답 오류 (HTTP 401)"
        )
        mock_sync_playwright.return_value.__enter__.return_value = MagicMock()

        with patch.object(monitor, "STATUS_FILE", "missing-monitor-status.json"):
            monitor.main()

        mock_send_telegram.assert_called_once_with(
            "❌ Benecafe 데이터 수집 실패\n"
            "원인: 데이터 API 응답 오류 (HTTP 401)"
        )

    def test_exception_summary_does_not_include_multiline_details(self):
        error = RuntimeError("첫 줄 원인\n민감할 수 있는 상세 로그")

        self.assertEqual(monitor.summarize_exception(error), "첫 줄 원인")

    @patch("monitor.send_telegram")
    @patch("monitor.sync_playwright", side_effect=RuntimeError("실행 파일 없음"))
    def test_playwright_start_failure_is_sent_to_bot(
        self,
        _mock_sync_playwright,
        mock_send_telegram,
    ):
        with patch.object(monitor, "STATUS_FILE", "missing-monitor-status.json"):
            monitor.main()

        mock_send_telegram.assert_called_once_with(
            "❌ Benecafe 데이터 수집 실패\n"
            "원인: 모니터링 실행 환경 준비 실패: 실행 파일 없음"
        )


if __name__ == "__main__":
    unittest.main()

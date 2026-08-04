import calendar
from datetime import date, datetime


WELFARECARD_DEMAND_URL = (
    "https://rga.benecafe.co.kr/mywel/getWelfarecardDemandListVer"
    "?crdcoNo=HA&rtnTpCd=&crtcrdProdNo=&ecluCrtcrdRealHhAskYn=N&necluCrtcrdRealHhAskYn=N"
    "&searchStartDate={search_start_date}&searchEndDate={search_end_date}"
    "&applStatCd=00&alreadyApplicationExclustion=&multiCrtcrdRealYn=false&adminPswd="
)


def subtract_one_month(target_date: date) -> date:
    """기준일에서 달력 기준으로 한 달 전 날짜를 계산합니다."""
    if target_date.month == 1:
        year = target_date.year - 1
        month = 12
    else:
        year = target_date.year
        month = target_date.month - 1

    day = min(target_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def build_welfarecard_demand_url(reference_date: date | None = None) -> str:
    """조회 시작일과 종료일을 반영한 복지카드 신청 목록 URL을 생성합니다."""
    search_end_date = reference_date or datetime.now().date()
    search_start_date = subtract_one_month(search_end_date)
    return WELFARECARD_DEMAND_URL.format(
        search_start_date=search_start_date.isoformat(),
        search_end_date=search_end_date.isoformat(),
    )

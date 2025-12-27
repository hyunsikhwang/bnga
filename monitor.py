import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# 설정: ntfy 토픽 (본인의 토픽으로 변경 가능하나 요청하신 주소 사용)
NTFY_TOPIC = "stock-info"
DATA_FILE = "latest_data.json"

def send_ntfy(message):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={"Title": "Benecafe 변경 감지", "Priority": "high"}
        )
        print(f"[Notification] Sent: {message}")
    except Exception as e:
        print(f"[Notification] Error: {e}")

def run_benecafe(playwright):
    # Github Secrets에서 환경변수로 불러옴
    user_id = os.environ.get("BENECAFE_ID")
    user_pw = os.environ.get("BENECAFE_PW")

    if not user_id or not user_pw:
        raise ValueError("아이디 또는 비밀번호가 환경변수에 설정되지 않았습니다.")

    browser = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    # 로케일 및 타임존 설정
    context = browser.new_context(
        ignore_https_errors=True, 
        timezone_id="Asia/Seoul", 
        locale="ko-KR",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    )
    context.set_default_timeout(60_000)
    page = context.new_page()

    try:
        print("1. 로그인 페이지 이동 중...")
        page.goto("https://cert.benecafe.co.kr/member/login?&cmpyNo=AA5", wait_until="domcontentloaded")

        print("2. 로그인 정보 입력 중...")
        page.get_by_placeholder("아이디").fill(user_id)
        page.get_by_placeholder("비밀번호").fill(user_pw)
        page.get_by_role("link", name="로그인", exact=True).click()

        print("3. 로그인 완료 대기 중...")
        # 로그인 성공 지표
        page.wait_for_selector('text="나의정보"', timeout=60_000)

        # 팝업 닫기 시도
        try:
            close_btn = page.get_by_role("link", name="닫기")
            if close_btn.count() > 0:
                close_btn.first.click()
        except:
            pass

        # 4. API 호출을 위한 날짜 계산 (오늘 기준 최근 1달)
        today_str = datetime.now().strftime("%Y-%m-%d")
        last_month_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        print(f"4. 데이터 조회 중 ({last_month_str} ~ {today_str})...")

        # API URL 구성 (날짜 동적 할당)
        api_url = (
            "https://rga.benecafe.co.kr/mywel/getWelfarecardDemandListVer"
            "?crdcoNo=HA&rtnTpCd=&crtcrdProdNo=&ecluCrtcrdRealHhAskYn=N&necluCrtcrdRealHhAskYn=N"
            f"&searchStartDate={last_month_str}&searchEndDate={today_str}"
            "&applStatCd=00&alreadyApplicationExclustion=&multiCrtcrdRealYn=false&adminPswd="
        )

        resp = context.request.get(api_url, timeout=60_000)
        print(f"[API Status] {resp.status}")

        if resp.status != 200:
            raise RuntimeError(f"Benecafe API Error: {resp.status}")

        return resp.json()  # JSON 형태로 반환

    except Exception as e:
        print(f"[Error] {e}")
        # 에러 발생 시 디버깅용 스크린샷 (Github Actions Artifact로 확인 가능하게 하려면 경로 설정 필요)
        return None
    finally:
        context.close()
        browser.close()

def main():
    with sync_playwright() as playwright:
        current_data = run_benecafe(playwright)

    if not current_data:
        print("데이터를 가져오지 못했습니다.")
        return

    # 기존 데이터 로드
    previous_data = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                previous_data = json.load(f)
        except:
            pass

    # 비교 로직 (단순 문자열 비교 또는 특정 키 비교)
    # 여기서는 JSON 전체 구조가 바뀌었는지 확인합니다.
    current_json_str = json.dumps(current_data, sort_keys=True, ensure_ascii=False)
    prev_json_str = json.dumps(previous_data, sort_keys=True, ensure_ascii=False) if previous_data else ""

    if current_json_str != prev_json_str:
        print("!! 변경 사항 감지 !!")
        
        # 상세 변경 내용을 알림에 포함하고 싶다면 파싱해서 메시지를 만드세요.
        # 예시: 간단히 알림만 발송
        send_ntfy(f"Benecafe 복지카드 내역 변동 감지!\n확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        # 상태 업데이트 (파일 저장)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(current_json_str)
    else:
        print("변경 사항 없음.")

if __name__ == "__main__":
    main()
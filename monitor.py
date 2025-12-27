import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# 설정: ntfy 토픽
NTFY_TOPIC = "stock-info"
DATA_FILE = "latest_data.json"

# 1. 텔레그램 알림 함수 추가
def send_telegram(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    # 설정이 없으면 텔레그램 전송 건너뜀
    if not token or not chat_id:
        print("[Telegram] 토큰 또는 Chat ID가 설정되지 않았습니다.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            print(f"[Telegram] Sent: {message}")
        else:
            print(f"[Telegram] Failed: {resp.text}")
    except Exception as e:
        print(f"[Telegram] Error: {e}")

# 2. 기존 ntfy 알림 함수
def send_ntfy(message, title="Benecafe 알림", priority="default"):
    try:
        headers = {
            "Title": title.encode('utf-8'),
            "Priority": priority
        }
        
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers=headers
        )
        print(f"[Ntfy] Sent: {message}")
    except Exception as e:
        print(f"[Ntfy] Error: {e}")

def run_benecafe(playwright):
    user_id = os.environ.get("BENECAFE_ID")
    user_pw = os.environ.get("BENECAFE_PW")

    if not user_id or not user_pw:
        raise ValueError("아이디 또는 비밀번호가 환경변수에 설정되지 않았습니다.")

    browser = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
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
        page.wait_for_selector('text="나의정보"', timeout=60_000)

        try:
            close_btn = page.get_by_role("link", name="닫기")
            if close_btn.count() > 0:
                close_btn.first.click()
        except:
            pass

        today_str = datetime.now().strftime("%Y-%m-%d")
        last_month_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        print(f"4. 데이터 조회 중 ({last_month_str} ~ {today_str})...")

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

        return resp.json()

    except Exception as e:
        print(f"[Error] {e}")
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

    previous_data = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                previous_data = json.load(f)
        except:
            pass

    current_json_str = json.dumps(current_data, sort_keys=True, ensure_ascii=False)
    prev_json_str = json.dumps(previous_data, sort_keys=True, ensure_ascii=False) if previous_data else ""

    check_time = datetime.now().strftime('%H:%M')

    if current_json_str != prev_json_str:
        print("!! 변경 사항 감지 !!")
        
        # 메시지 내용 구성
        msg_body = f"Benecafe 복지카드 내역 변동 감지!\n확인 시간: {check_time}"
        
        # 1. Ntfy 전송
        send_ntfy(
            msg_body,
            title="Benecafe 변경 발생 🚨",
            priority="high"
        )
        # 2. Telegram 전송
        send_telegram(f"🚨 {msg_body}")
        
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(current_json_str)
    else:
        print("변경 사항 없음.")
        
        # 메시지 내용 구성
        msg_body = f"변경 사항 없음.\n확인 시간: {check_time}"

        # 1. Ntfy 전송
        send_ntfy(
            msg_body,
            title="Benecafe 모니터링",
            priority="low"
        )
        # 2. Telegram 전송 (필요 없으면 주석 처리 가능)
        send_telegram(f"✅ {msg_body}")

if __name__ == "__main__":
    main()
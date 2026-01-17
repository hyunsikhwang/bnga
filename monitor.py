import os
import json
import time
import requests
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------
# 설정값
# ---------------------------------------------------------
NTFY_TOPIC = "stock-info"
DATA_FILE = "latest_data.json"
STATUS_FILE = "monitor_status.json"

# 시간 설정 (초 단위)
INTERVAL_NORMAL = 3600    # 1시간
INTERVAL_IDLE = 86400     # 24시간
HEARTBEAT_INTERVAL = 86400 # 24시간 (생존신고 주기)

# 24번(24시간) 연속 변경 없으면 24시간 간격으로 전환
THRESHOLD_TO_IDLE = 24    

# ---------------------------------------------------------
# 알림 함수
# ---------------------------------------------------------
def send_telegram(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[Telegram] Error: {e}")

def send_ntfy(message, title="Benecafe 알림", priority="default"):
    try:
        headers = {"Title": title.encode('utf-8'), "Priority": priority}
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers=headers,
            timeout=10
        )
    except Exception as e:
        print(f"[Ntfy] Error: {e}")

def send_alert(msg, title="알림", priority="default"):
    print(f"[Alert] {msg}")
    send_ntfy(msg, title, priority)
    send_telegram(f"[{title}] {msg}")

# ---------------------------------------------------------
# 데이터 처리 및 비교 헬퍼 함수 (핵심 수정 부분)
# ---------------------------------------------------------
def get_welfare_list(data):
    """
    JSON 구조:
    {
        "resultMap": {
            "welfarecardDemandList": [ ... ]
        }
    }
    경로에 맞춰 리스트를 추출합니다.
    """
    try:
        if not data:
            return []
        
        # 제공된 JSON 구조 반영
        result_map = data.get("resultMap")
        if result_map and isinstance(result_map, dict):
            return result_map.get("welfarecardDemandList", [])
        
        return []
    except Exception as e:
        print(f"[Parse Error] 데이터 구조 분석 실패: {e}")
        return []

def get_item_id(item):
    """
    고유 식별자 'applSeq'를 반환합니다.
    """
    return str(item.get("applSeq", ""))

def format_currency(value):
    try:
        return f"{int(value):,}원"
    except:
        return str(value)

def compare_data(prev_data, curr_data):
    """
    이전 데이터와 현재 데이터를 비교하여 유의미한 변경(신규, 상태변경)만 추출합니다.
    삭제된 항목(기간 경과)은 무시합니다.
    """
    prev_list = get_welfare_list(prev_data)
    curr_list = get_welfare_list(curr_data)

    # ID 기준으로 딕셔너리 변환 (applSeq -> Item)
    prev_map = {get_item_id(item): item for item in prev_list if get_item_id(item)}
    curr_map = {get_item_id(item): item for item in curr_list if get_item_id(item)}

    changes = []
    
    # 현재 리스트를 순회하며 확인
    for item_id, curr_item in curr_map.items():
        curr_stat = curr_item.get('cstApplStatNm', '미상')  # 상태값 (예: 전송완료)
        merch_nm = curr_item.get('mcnsNm', '알수없음')       # 가맹점명 (예: 네이버페이)
        amount = format_currency(curr_item.get('usePrc', 0)) # 사용금액

        if item_id not in prev_map:
            # [CASE 1] 신규 항목 발견
            changes.append(f"🆕 [신규] {merch_nm} / {amount} ({curr_stat})")
        else:
            # [CASE 2] 기존 항목 존재 -> 상태 비교
            prev_item = prev_map[item_id]
            prev_stat = prev_item.get('cstApplStatNm', '미상')
            
            if curr_stat != prev_stat:
                changes.append(f"🔄 [상태변경] {merch_nm}: {prev_stat} ➔ {curr_stat}")

    # 삭제된 항목은 무시 (알림 없음)
    
    return changes

# ---------------------------------------------------------
# 베네카페 크롤링 로직
# ---------------------------------------------------------
def run_benecafe(playwright):
    user_id = os.environ.get("BENECAFE_ID")
    user_pw = os.environ.get("BENECAFE_PW")

    if not user_id or not user_pw:
        print("환경변수 미설정")
        return None

    browser = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context(
        ignore_https_errors=True, 
        timezone_id="Asia/Seoul", 
        locale="ko-KR",
        user_agent="Mozilla/5.0"
    )
    context.set_default_timeout(60_000)
    page = context.new_page()

    try:
        page.goto("https://cert.benecafe.co.kr/member/login?&cmpyNo=AA5", wait_until="domcontentloaded")
        page.get_by_placeholder("아이디").fill(user_id)
        page.get_by_placeholder("비밀번호").fill(user_pw)
        page.get_by_role("link", name="로그인", exact=True).click()

        # 비밀번호 변경 페이지 처리
        try:
            # 비밀번호 변경 페이지가 로드될 시간을 기다림
            page.wait_for_timeout(5000)

            # 비밀번호 변경 페이지인지 확인
            if page.get_by_text("비밀번호변경").count() > 0:
                print("비밀번호 변경 페이지 감지 - '다음에 변경하기' 버튼 클릭")
                page.get_by_role("link", name="다음에 변경하기").click()
                page.wait_for_selector('text="나의정보"', timeout=60_000)
            else:
                page.wait_for_selector('text="나의정보"', timeout=60_000)
        except Exception as e:
            print(f"[비밀번호 변경 페이지 처리 오류] {e}")
            pass

        try:
            if page.get_by_role("link", name="닫기").count() > 0:
                page.get_by_role("link", name="닫기").first.click()
        except:
            pass

        today_str = datetime.now().strftime("%Y-%m-%d")
        last_month_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        api_url = (
            "https://rga.benecafe.co.kr/mywel/getWelfarecardDemandListVer"
            "?crdcoNo=HA&rtnTpCd=&crtcrdProdNo=&ecluCrtcrdRealHhAskYn=N&necluCrtcrdRealHhAskYn=N"
            f"&searchStartDate={last_month_str}&searchEndDate={today_str}"
            "&applStatCd=00&alreadyApplicationExclustion=&multiCrtcrdRealYn=false&adminPswd="
        )

        resp = context.request.get(api_url, timeout=60_000)
        if resp.status != 200:
            return None
        return resp.json()

    except Exception as e:
        print(f"[Error] {e}")
        return None
    finally:
        context.close()
        browser.close()

# ---------------------------------------------------------
# 메인 로직
# ---------------------------------------------------------
def main():
    # 1. 상태 로드
    status = {
        "last_check_ts": 0, 
        "no_change_count": 0, 
        "last_heartbeat_ts": 0
    }
    
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                loaded_status = json.load(f)
                status.update(loaded_status)
        except:
            pass

    last_check_ts = status.get("last_check_ts", 0)
    no_change_count = status.get("no_change_count", 0)
    last_heartbeat_ts = status.get("last_heartbeat_ts", 0)
    current_ts = time.time()

    # 2. 현재 모드 결정
    if no_change_count >= THRESHOLD_TO_IDLE:
        required_interval = INTERVAL_IDLE
        mode_str = "🌙 절전 모드 (24시간)"
    else:
        required_interval = INTERVAL_NORMAL
        mode_str = "⚡ 일반 모드 (1시간)"

    # 3. 실행 시간 체크
    time_since = current_ts - last_check_ts
    if time_since < required_interval:
        next_run = datetime.fromtimestamp(last_check_ts + required_interval)
        print(f"⏳ [{mode_str}] 대기 중... (다음 실행: {next_run.strftime('%H:%M:%S')})")
        return

    # 4. 크롤링 수행
    print(f"🚀 [{mode_str}] 확인 시작...")
    with sync_playwright() as playwright:
        current_data = run_benecafe(playwright)

    if not current_data:
        print("❌ 데이터 수집 실패")
        send_telegram("❌ Benecafe 데이터 수집 실패")
        return

    # 5. 데이터 비교 로직
    previous_data = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                previous_data = json.load(f)
        except:
            pass
    
    # 변경 사항 감지
    change_logs = compare_data(previous_data, current_data)
    
    # 파일 저장을 위한 JSON 문자열 (항상 최신 데이터로 덮어쓰기)
    current_json_str = json.dumps(current_data, sort_keys=True, ensure_ascii=False)
    
    check_time = datetime.now().strftime('%H:%M')

    if change_logs:
        # [변경 발생: 신규 추가 또는 상태 변경]
        print(f"!! 변경 사항 감지 !! ({len(change_logs)}건)")
        for log in change_logs:
            print(log)

        # 데이터 파일 갱신
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(current_json_str)

        # 알림 메시지 구성
        alert_msg = f"확인 시간: {check_time}\n" + "\n".join(change_logs)
        send_alert(alert_msg, title="Benecafe 변동 🚨", priority="high")
        
        status["no_change_count"] = 0
        status["last_heartbeat_ts"] = current_ts 
        
    else:
        # [변경 없음]
        # 데이터 파일은 최신 상태로 갱신 (삭제된 항목 반영을 위해)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(current_json_str)

        status["no_change_count"] += 1
        print(f"✅ 유의미한 변경 없음 (연속 {status['no_change_count']}회)")
        
        # 1) 모드 전환 알림
        if status["no_change_count"] == THRESHOLD_TO_IDLE:
            send_alert(f"24시간 동안 변경 없음. 24시간 간격으로 전환합니다.", title="모드 변경 🌙", priority="low")
            status["last_heartbeat_ts"] = current_ts 
            
        # 2) 생존 신고
        elif current_ts - last_heartbeat_ts >= HEARTBEAT_INTERVAL:
            send_alert(
                f"현재 모니터링 정상 작동 중입니다.\n(현재 모드: {mode_str})", 
                title="생존 신고 👋", 
                priority="min"
            )
            status["last_heartbeat_ts"] = current_ts

    # 6. 상태 저장
    status["last_check_ts"] = current_ts
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)

if __name__ == "__main__":
    main()

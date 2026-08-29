# Benecafe 수집 실패 원인 알림

- [x] 기존 수집 실패 처리와 Telegram 봇 알림 경로 확인
- [x] 수집 단계별 오류 원인을 보존하고 사용자용 메시지로 구성
- [x] 오류 메시지 회귀 테스트 추가
- [x] 전체 테스트 및 변경 사항 점검
- [x] 한국어 커밋 후 현재 브랜치 푸시

## Review

- 환경변수 누락, 브라우저·로그인·API 단계 오류를 `BenecafeCollectionError`로 구분했습니다.
- Telegram 실패 알림에 `원인:` 줄을 추가하고 다중 행 예외 상세는 첫 줄로 제한했습니다.
- 검증: `.venv/bin/python -m unittest -v` (8개 테스트 통과)

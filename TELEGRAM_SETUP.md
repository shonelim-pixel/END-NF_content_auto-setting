# 🤖 텔레그램 봇 설정 가이드

END NF 자동 콘텐츠 시스템에서 글 초안을 텔레그램으로 받기 위한 설정입니다.

## 1단계: 텔레그램 봇 만들기

1. 텔레그램에서 `@BotFather` 검색 → 대화 시작
2. `/newbot` 입력
3. 봇 이름 입력: `END NF Content Bot`
4. 봇 유저네임 입력: `endnf_content_bot` (고유해야 함, 이미 있으면 다른 이름)
5. **봇 토큰**이 생성됩니다 → 복사해서 보관

   ```
   예시: 7123456789:AAH-abcdefgh123456789_AbCdEfGhIjKlMn
   ```

## 2단계: 채팅 ID 확인

1. 생성된 봇에게 아무 메시지 보내기 (예: "hello")
2. 브라우저에서 아래 URL 접속 (토큰 부분 교체):
   ```
   https://api.telegram.org/bot{YOUR_BOT_TOKEN}/getUpdates
   ```
3. 응답에서 `"chat": {"id": 123456789}` 부분의 숫자가 **채팅 ID**

## 3단계: GitHub Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions

| Secret Name | 값 |
|------------|-----|
| `TELEGRAM_BOT_TOKEN` | 1단계에서 받은 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 2단계에서 확인한 채팅 ID |
| `ANTHROPIC_API_KEY` | Claude API 키 |

## 4단계: 테스트

로컬에서 테스트:
```bash
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
python notification_sender.py --test
```

## (선택) 이메일 설정

Gmail 앱 비밀번호 사용을 권장합니다.

| Secret Name | 값 |
|------------|-----|
| `SMTP_USER` | Gmail 주소 |
| `SMTP_PASS` | Gmail 앱 비밀번호 (2단계 인증 필요) |
| `NOTIFY_EMAIL` | 수신할 이메일 주소 |

## 수신 메시지 예시

텔레그램으로 이런 형태의 메시지가 도착합니다:

```
📮 END NF 카페 글 초안
━━━━━━━━━━━━━━━━━━━━━━
📅 💊 목요일: NF 치료제 개발 동향 / 임상시험 소식
📊 참고 데이터: 4건
━━━━━━━━━━━━━━━━━━━━━━

END NF 션입니다 🙏

(글 본문...)

━━━━━━━━━━━━━━━━━━━━━━
🎨 이미지 프롬프트

📌 빛나는 치료제 — 코셀루고의 희망
glowing medicine capsule with warm hopeful light...

━━━━━━━━━━━━━━━━━━━━━━
✏️ 다음 단계
1. 위 글 검토/수정
2. 이미지 프롬프트로 나노바나나/그록에서 이미지 생성
3. 네이버 카페에 글+이미지 게시
```

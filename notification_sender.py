"""
============================================================
END NF 콘텐츠 시스템 - 텔레그램/이메일 전송기 (5단계)
============================================================
생성된 카페 글 초안 + 이미지 프롬프트를 수현님에게 전송합니다.
검토 후 네이버 카페에 직접 게시하는 워크플로우.

사용법:
    python notification_sender.py --day thu                         # 오늘 결과 전송
    python notification_sender.py --input output/post_thu_20260301.json  # 특정 파일 전송
    python notification_sender.py --test                            # 테스트 메시지 전송
    python notification_sender.py --channel telegram                # 텔레그램만
    python notification_sender.py --channel email                   # 이메일만
    python notification_sender.py --channel all                     # 전체 채널

환경변수:
    TELEGRAM_BOT_TOKEN: 텔레그램 봇 토큰 (필수)
    TELEGRAM_CHAT_ID: 수현님 텔레그램 채팅 ID (필수)
    SMTP_HOST: SMTP 서버 (선택, 이메일 전송 시)
    SMTP_PORT: SMTP 포트 (기본 587)
    SMTP_USER: SMTP 사용자
    SMTP_PASS: SMTP 비밀번호
    NOTIFY_EMAIL: 수신 이메일 주소
"""

import os
import sys
import json
import argparse
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode, quote
    from urllib.error import HTTPError, URLError
except ImportError:
    pass

# ── 설정 ──
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("endnf.notify")

# 텔레그램 메시지 길이 제한
TG_MAX_LENGTH = 4096


# ============================================================
# 텔레그램 전송기
# ============================================================
class TelegramSender:
    """텔레그램 봇 API를 통한 메시지 전송"""

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        텔레그램 메시지 전송

        Args:
            text: 메시지 본문 (HTML 또는 Markdown)
            parse_mode: HTML 또는 MarkdownV2

        Returns:
            성공 여부
        """
        if not self.is_configured:
            logger.warning("⚠️ 텔레그램 설정 없음 (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
            return False

        # 길이 제한 처리
        messages = self._split_message(text, TG_MAX_LENGTH)

        success = True
        for i, msg in enumerate(messages):
            try:
                data = json.dumps({
                    "chat_id": self.chat_id,
                    "text": msg,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                }).encode("utf-8")

                req = Request(
                    f"{self.base_url}/sendMessage",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                response = urlopen(req, timeout=30)
                result = json.loads(response.read().decode())

                if result.get("ok"):
                    logger.info(f"  ✅ 텔레그램 전송 성공 ({i+1}/{len(messages)})")
                else:
                    logger.error(f"  ❌ 텔레그램 전송 실패: {result}")
                    success = False

            except (HTTPError, URLError) as e:
                logger.error(f"  ❌ 텔레그램 API 오류: {e}")
                success = False
            except Exception as e:
                logger.error(f"  ❌ 텔레그램 전송 예외: {e}")
                success = False

        return success

    def _split_message(self, text: str, max_length: int) -> list:
        """긴 메시지를 텔레그램 제한에 맞게 분할"""
        if len(text) <= max_length:
            return [text]

        messages = []
        lines = text.split("\n")
        current = ""

        for line in lines:
            if len(current) + len(line) + 1 > max_length - 50:  # 여유분 50자
                if current:
                    messages.append(current.strip())
                    current = f"(계속)\n\n{line}\n"
                else:
                    # 한 줄이 너무 긴 경우
                    messages.append(line[:max_length - 50])
                    current = line[max_length - 50:] + "\n"
            else:
                current += line + "\n"

        if current.strip():
            messages.append(current.strip())

        return messages


# ============================================================
# 이메일 전송기
# ============================================================
class EmailSender:
    """SMTP를 통한 이메일 전송"""

    def __init__(self):
        self.host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER", "")
        self.password = os.environ.get("SMTP_PASS", "")
        self.to_email = os.environ.get("NOTIFY_EMAIL", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.user and self.password and self.to_email)

    def send(self, subject: str, body_html: str) -> bool:
        """
        이메일 전송

        Args:
            subject: 제목
            body_html: HTML 본문

        Returns:
            성공 여부
        """
        if not self.is_configured:
            logger.warning("⚠️ 이메일 설정 없음 (SMTP_USER, SMTP_PASS, NOTIFY_EMAIL)")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.user
            msg["To"] = self.to_email

            html_part = MIMEText(body_html, "html", "utf-8")
            msg.attach(html_part)

            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)

            logger.info("  ✅ 이메일 전송 성공")
            return True

        except Exception as e:
            logger.error(f"  ❌ 이메일 전송 실패: {e}")
            return False


# ============================================================
# 메시지 포매터
# ============================================================
class MessageFormatter:
    """전송 채널별 메시지 포맷 변환"""

    @staticmethod
    def format_telegram(post_data: dict) -> str:
        """텔레그램 HTML 형식"""
        day = post_data.get("day", "")
        title = post_data.get("title", "END NF 콘텐츠")
        content = post_data.get("content", "")
        image_prompt = post_data.get("image_prompt", "")
        img_structured = post_data.get("image_prompts_structured", [])
        generated_at = post_data.get("generated_at", "")[:16]
        items_count = post_data.get("input_items_count", 0)

        # HTML 태그 이스케이프 (텔레그램 HTML 모드)
        content_escaped = (content
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        parts = []

        # 헤더
        parts.append(f"📮 <b>END NF 카페 글 초안</b>")
        parts.append(f"━━━━━━━━━━━━━━━━━━━━━━")
        parts.append(f"📅 {title}")
        parts.append(f"📊 참고 데이터: {items_count}건")
        parts.append(f"🕐 생성: {generated_at}")
        parts.append(f"━━━━━━━━━━━━━━━━━━━━━━\n")

        # 본문 (텔레그램 제한 고려해 축약)
        if len(content_escaped) > 2500:
            parts.append(content_escaped[:2500])
            parts.append("\n\n<i>... (전문은 이메일/파일 확인)</i>")
        else:
            parts.append(content_escaped)

        # 이미지 프롬프트
        parts.append(f"\n\n━━━━━━━━━━━━━━━━━━━━━━")
        parts.append(f"🎨 <b>이미지 프롬프트</b>\n")

        if img_structured:
            for p in img_structured[:2]:  # 최대 2개만 표시
                desc = p.get("description_ko", "")
                prompt = p.get("prompt_en", "")
                parts.append(f"📌 {desc}")
                parts.append(f"<code>{prompt[:200]}</code>\n")
        elif image_prompt and image_prompt != "(미리보기 모드)":
            parts.append(f"<code>{image_prompt[:300]}</code>")

        # 액션 가이드
        parts.append(f"\n━━━━━━━━━━━━━━━━━━━━━━")
        parts.append(f"✏️ <b>다음 단계</b>")
        parts.append(f"1. 위 글 검토/수정")
        parts.append(f"2. 이미지 프롬프트로 나노바나나/그록에서 이미지 생성")
        parts.append(f"3. 네이버 카페에 글+이미지 게시")
        parts.append(f"\n💙 END NF, 함께하면 이겨낼 수 있습니다")

        return "\n".join(parts)

    @staticmethod
    def format_email(post_data: dict) -> tuple:
        """이메일 HTML 형식 (subject, body)"""
        day = post_data.get("day", "")
        title = post_data.get("title", "END NF 콘텐츠")
        content = post_data.get("content", "")
        image_prompt = post_data.get("image_prompt", "")
        img_structured = post_data.get("image_prompts_structured", [])
        negative = post_data.get("negative_prompt", "")
        generated_at = post_data.get("generated_at", "")[:16]
        items_count = post_data.get("input_items_count", 0)

        subject = f"[END NF] {title} - 카페 글 초안 검토 요청"

        # 본문 줄바꿈 → <br>
        content_html = content.replace("\n", "<br>")

        # 이미지 프롬프트 HTML
        img_section = ""
        if img_structured:
            img_items = ""
            for p in img_structured:
                desc = p.get("description_ko", "")
                prompt = p.get("prompt_en", "")
                ratio = p.get("aspect_ratio", "1:1")
                img_items += f"""
                <tr>
                    <td style="padding:8px;border-bottom:1px solid #eee;">{desc}</td>
                    <td style="padding:8px;border-bottom:1px solid #eee;font-family:monospace;font-size:12px;background:#f5f5f5;">{prompt}</td>
                    <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{ratio}</td>
                </tr>
                """
            img_section = f"""
            <h3 style="color:#4A90D9;">🎨 이미지 프롬프트</h3>
            <table style="width:100%;border-collapse:collapse;margin:10px 0;">
                <tr style="background:#4A90D9;color:white;">
                    <th style="padding:8px;">설명</th>
                    <th style="padding:8px;">프롬프트 (복사용)</th>
                    <th style="padding:8px;">비율</th>
                </tr>
                {img_items}
            </table>
            """
            if negative:
                img_section += f"""
                <p><strong>네거티브 프롬프트:</strong><br>
                <code style="background:#fff0f0;padding:4px;">{negative}</code></p>
                """
        elif image_prompt and image_prompt != "(미리보기 모드)":
            img_section = f"""
            <h3 style="color:#4A90D9;">🎨 이미지 프롬프트</h3>
            <pre style="background:#f5f5f5;padding:12px;border-radius:4px;font-size:13px;">{image_prompt}</pre>
            """

        body = f"""
        <html>
        <body style="font-family:'Pretendard',sans-serif;max-width:700px;margin:0 auto;padding:20px;">
            <div style="background:#4A90D9;color:white;padding:20px;border-radius:8px 8px 0 0;">
                <h1 style="margin:0;font-size:20px;">📮 END NF 카페 글 초안</h1>
                <p style="margin:5px 0 0;opacity:0.9;">{title}</p>
            </div>

            <div style="background:#f8f9fa;padding:15px;border:1px solid #e0e0e0;">
                <span>📊 참고 데이터: <strong>{items_count}건</strong></span> &nbsp;|&nbsp;
                <span>🕐 생성: {generated_at}</span>
            </div>

            <div style="padding:20px;border:1px solid #e0e0e0;border-top:none;">
                <h2 style="color:#1A1F36;">✍️ 글 초안</h2>
                <div style="background:white;padding:20px;border:1px solid #e8e8e8;border-radius:4px;line-height:1.8;">
                    {content_html}
                </div>
            </div>

            <div style="padding:20px;border:1px solid #e0e0e0;border-top:none;">
                {img_section}
            </div>

            <div style="background:#FFF8F0;padding:20px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
                <h3 style="color:#F5A623;">✏️ 다음 단계</h3>
                <ol style="line-height:2;">
                    <li>위 글을 검토하고 필요 시 수정해주세요</li>
                    <li>이미지 프롬프트를 나노바나나 또는 그록에 붙여넣어 이미지를 생성해주세요</li>
                    <li>네이버 카페에 글 + 이미지를 게시해주세요</li>
                </ol>
                <p style="text-align:center;color:#4A90D9;font-weight:bold;">
                    💙 END NF, 함께하면 이겨낼 수 있습니다
                </p>
            </div>
        </body>
        </html>
        """

        return subject, body


# ============================================================
# 알림 관리자
# ============================================================
class NotificationManager:
    """통합 알림 매니저"""

    def __init__(self):
        self.telegram = TelegramSender()
        self.email = EmailSender()
        self.formatter = MessageFormatter()

    def send(self, post_data: dict, channels: list = None) -> dict:
        """
        생성된 콘텐츠를 알림 채널로 전송

        Args:
            post_data: content_generator 출력 딕셔너리
            channels: ["telegram", "email"] 또는 None (전체)

        Returns:
            채널별 성공 여부
        """
        if channels is None:
            channels = ["telegram", "email"]

        results = {}

        print(f"\n{'='*60}")
        print(f"📮 콘텐츠 전송")
        print(f"   제목: {post_data.get('title', 'N/A')}")
        print(f"   채널: {', '.join(channels)}")
        print(f"{'='*60}")

        # 텔레그램
        if "telegram" in channels:
            if self.telegram.is_configured:
                tg_message = self.formatter.format_telegram(post_data)
                results["telegram"] = self.telegram.send_message(tg_message)
            else:
                print("  ⏭️ 텔레그램 건너뜀 (미설정)")
                results["telegram"] = None

        # 이메일
        if "email" in channels:
            if self.email.is_configured:
                subject, body = self.formatter.format_email(post_data)
                results["email"] = self.email.send(subject, body)
            else:
                print("  ⏭️ 이메일 건너뜀 (미설정)")
                results["email"] = None

        # 결과 요약
        print(f"\n📊 전송 결과:")
        for ch, ok in results.items():
            if ok is True:
                print(f"  ✅ {ch}: 성공")
            elif ok is False:
                print(f"  ❌ {ch}: 실패")
            else:
                print(f"  ⏭️ {ch}: 미설정 (건너뜀)")

        return results

    def send_test(self, channels: list = None) -> dict:
        """테스트 메시지 전송"""
        test_data = {
            "day": "test",
            "title": "🧪 테스트 메시지",
            "content": "END NF 션입니다 🙏\n\n이것은 END NF 자동 콘텐츠 시스템의 테스트 메시지입니다.\n\n이 메시지가 정상적으로 도착했다면, 시스템이 올바르게 설정된 것입니다.\n\nEND NF, 함께하면 이겨낼 수 있습니다 💙\n\n#ENDNF #신경섬유종 #시스템테스트",
            "image_prompt": "Test image prompt - warm illustration of connected community",
            "image_prompts_structured": [
                {
                    "description_ko": "테스트 이미지: 따뜻한 커뮤니티",
                    "prompt_en": "warm community illustration, people holding hands, soft pastel colors, hopeful atmosphere",
                    "aspect_ratio": "1:1",
                }
            ],
            "input_items_count": 0,
            "generated_at": datetime.now().isoformat(),
        }

        print("🧪 테스트 메시지 전송")
        return self.send(test_data, channels)

    def send_error_alert(self, error_message: str, day: str = "") -> bool:
        """에러 발생 시 알림"""
        if not self.telegram.is_configured:
            return False

        alert = (
            f"🚨 <b>END NF 시스템 오류 알림</b>\n\n"
            f"📅 요일: {day or 'N/A'}\n"
            f"🕐 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"❌ 오류: {error_message}\n\n"
            f"시스템 로그를 확인해주세요."
        )

        return self.telegram.send_message(alert)

    def send_daily_summary(self, collection_result: dict) -> bool:
        """일일 수집 결과 요약 전송 (생성 전 확인용)"""
        if not self.telegram.is_configured:
            return False

        day = collection_result.get("day", "")
        title = collection_result.get("title", "")
        total = collection_result.get("total_items", 0)
        tasks = collection_result.get("task_results", {})
        errors = collection_result.get("errors", [])

        parts = [
            f"📊 <b>일일 수집 완료</b>",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"📅 {title}",
            f"📦 총 수집: <b>{total}건</b>",
        ]

        for task, count in tasks.items():
            parts.append(f"  → {task}: {count}건")

        if errors:
            parts.append(f"\n⚠️ 오류 {len(errors)}건:")
            for err in errors:
                parts.append(f"  → {err['task']}: {err['error'][:100]}")

        parts.append(f"\n🤖 Claude API로 글 생성을 시작합니다...")

        return self.telegram.send_message("\n".join(parts))


# ============================================================
# CLI 실행
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="END NF 알림 전송기")
    parser.add_argument("--day", type=str, default="",
                        help="요일 (해당 요일 결과 파일 자동 탐색)")
    parser.add_argument("--input", type=str, default="",
                        help="전송할 포스팅 파일 경로")
    parser.add_argument("--channel", type=str, default="all",
                        choices=["telegram", "email", "all"],
                        help="전송 채널")
    parser.add_argument("--test", action="store_true",
                        help="테스트 메시지 전송")
    args = parser.parse_args()

    manager = NotificationManager()
    channels = None if args.channel == "all" else [args.channel]

    if args.test:
        manager.send_test(channels)
        return

    # 포스팅 데이터 로드
    post_data = None

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            post_data = json.load(f)
    elif args.day:
        # 오늘 날짜 기준 파일 탐색
        date_str = datetime.now().strftime("%Y%m%d")
        candidates = [
            os.path.join(OUTPUT_DIR, f"post_{args.day}_{date_str}.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    post_data = json.load(f)
                break

        if not post_data:
            print(f"❌ 포스팅 파일을 찾을 수 없습니다: {args.day}")
            print(f"   탐색 경로: {candidates}")
            return
    else:
        # 가장 최근 파일 탐색
        if os.path.exists(OUTPUT_DIR):
            json_files = sorted(
                [f for f in os.listdir(OUTPUT_DIR) if f.startswith("post_") and f.endswith(".json")],
                reverse=True,
            )
            if json_files:
                filepath = os.path.join(OUTPUT_DIR, json_files[0])
                with open(filepath, "r", encoding="utf-8") as f:
                    post_data = json.load(f)
                print(f"📂 최근 파일 사용: {json_files[0]}")

    if not post_data:
        print("❌ 전송할 포스팅 데이터가 없습니다.")
        print("   먼저 content_generator.py로 글을 생성해주세요.")
        return

    manager.send(post_data, channels)


if __name__ == "__main__":
    main()

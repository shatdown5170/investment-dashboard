import os
import requests
import numpy as np
from datetime import datetime
import yfinance as yf

# 환경변수에서 토큰/ID 가져오기 (GitHub Secrets)
TELEGRAM_TOKEN   = os.environ['TELEGRAM_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

DASHBOARD_URL = 'https://shatdown5170.github.io/investment-dashboard'

# ── 텔레그램 메시지 전송 ──────────────────────────────
def send_telegram(message):
    url  = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = {
        'chat_id':    TELEGRAM_CHAT_ID,
        'text':       message,
        'parse_mode': 'HTML'
    }
    r = requests.post(url, json=data, timeout=10)
    return r.json()

# ── RSI 계산 (Wilder's smoothing) ────────────────────
def calc_rsi(closes, period=14):
    closes = list(closes)
    if len(closes) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i-1]
        if d > 0: gains  += d
        else:     losses -= d
    avg_gain = gains  / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i-1]
        avg_gain = (avg_gain * (period-1) + (d  if d > 0 else 0)) / period
        avg_loss = (avg_loss * (period-1) + (-d if d < 0 else 0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

# ── 메인 ─────────────────────────────────────────────
def main():
    today = datetime.now().strftime('%Y년 %m월 %d일')

    # 2년치 데이터 (MA200 계산에 충분한 과거 데이터)
    try:
        qqq = yf.download('QQQ', period='2y', interval='1d', progress=False)
        if qqq.empty:
            raise ValueError('데이터 없음')
    except Exception as e:
        send_telegram(f'⚠️ QQQ 데이터 로드 실패\n오류: {e}')
        return

    closes = qqq['Close'].values.flatten().tolist()

    price   = round(float(closes[-1]), 2)
    ma200   = round(float(np.mean(closes[-200:])), 2)
    high52w = round(float(np.max(closes[-252:])), 2)
    rsi     = calc_rsi(closes[-100:])

    above_ma200   = price > ma200
    ma200_diff    = round((price - ma200) / ma200 * 100, 1)
    drawdown      = round((price - high52w) / high52w * 100, 1)

    # ── RSI 상태 텍스트 ──
    if   rsi <= 25: rsi_txt = '극과매도 🚨'
    elif rsi <= 40: rsi_txt = '과매도 ⚠️'
    elif rsi >= 70: rsi_txt = '과매수'
    else:           rsi_txt = '중립'

    # ── 매수 신호 판단 ──
    signals = []
    if not above_ma200:
        signals.append(('🟠 1차 신호', 'MA200 이탈 확인', '탄약고 15% → TQQQ 매수'))
    if drawdown <= -15:
        signals.append(('🔥 2차 신호', f'고점 대비 {drawdown}%', '탄약고 20% → TQQQ 매수'))
    if drawdown <= -25:
        signals.append(('🔥 3차 신호', f'고점 대비 {drawdown}%', '탄약고 25% → TQQQ 매수'))
    if drawdown <= -35 and rsi <= 25:
        signals.append(('🚨 4차 신호', f'고점 대비 {drawdown}% + RSI {rsi}', '탄약고 전량 → TQQQ 매수'))

    # ── TQQQ 매도 힌트 (RSI 과매수 구간) ──
    sell_hint = ''
    if rsi >= 70 and above_ma200:
        sell_hint = '\n⚠️ RSI 과매수 구간 — TQQQ 매도 조건 점검하세요'

    # ── MA200 상태 ──
    ma_status = '✅ MA200 위 (정상 구간)' if above_ma200 else f'⚠️ MA200 아래 ({ma200_diff}%)'

    # ── 메시지 조립 ──
    msg = (
        f'📊 <b>QLD·TQQQ 전략 알림</b>\n'
        f'{today}\n'
        f'─────────────────\n'
        f'<b>QQQ 현황</b>\n'
        f'현재가: <b>${price}</b>\n'
        f'MA200:  ${ma200} ({ma200_diff:+}%)\n'
        f'52주 고점: ${high52w}\n'
        f'낙폭: <b>{drawdown}%</b>\n'
        f'RSI: <b>{rsi}</b> ({rsi_txt})\n'
        f'상태: {ma_status}'
        f'{sell_hint}\n'
        f'─────────────────\n'
    )

    if signals:
        msg += '<b>🔔 매수 신호 발동!</b>\n'
        for title, detail, action in signals:
            msg += f'\n{title}\n{detail}\n→ {action}\n'
    else:
        msg += (
            '<b>오늘의 액션</b>\n'
            '💎 QLD 매일 55,000원 DCA 계속\n'
            'TQQQ 매수 조건 미충족 — 탄약고 적립 유지'
        )

    msg += f'\n─────────────────\n<a href="{DASHBOARD_URL}">📱 대시보드 열기</a>'

    result = send_telegram(msg)
    if result.get('ok'):
        print('✓ 텔레그램 알림 전송 완료')
    else:
        print(f'✗ 전송 실패: {result}')

if __name__ == '__main__':
    main()

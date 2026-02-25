import requests
import time
import smtplib
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
import pytz

# -------------------------------- 配置区域 -----------------------------------
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER', "smtp-mail.outlook.com")
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
# 支持多个收件人邮箱，用逗号分隔
RECEIVER_EMAILS_STR = os.getenv('RECEIVER_EMAIL', '')

RECEIVER_EMAILS = [email.strip() for email in RECEIVER_EMAILS_STR.split(',') if email.strip()]

DROP_THRESHOLD = -5.0

STOCK_SYMBOLS = ['AGQ', 'ORCL', 'LLY', 'NFLX', 'ABBV', 'IBKR', 'AMD', 'CRM', 'GLW', 'GS',
                 'MRK', 'MU', 'LITE', 'APP', 'NOW', 'LRCX', 'ANET', 'SNXX', 'BLK', 'QCOM',
                 'AMAT', 'INTC', 'SCHW', 'TXN', 'ISRG', 'PFE', 'KLAC', 'SCCO', 'CRWD', 'ADI',
                 'KKR', 'COIN', 'NEM', 'BMY', 'RBLX', 'SNOW', 'CVNA', 'EQIX', 'NET', 'MRVL',
                 'CRWV', 'MNST', 'VRT', 'EXC', 'ETR', 'EA', 'ZS', 'XEL', 'CVS', 'WDC']

# ---------------------------------------------------------------------------

def get_stock_quote(symbol):
    """从Finnhub API获取股票实时报价和前收盘价"""
    # 设置更严格的超时控制，防止单个请求卡死整个脚本
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        # 关键修改：为请求设置明确的超时时间（连接超时5秒，读取超时10秒）
        response = requests.get(url, timeout=(5, 10))
        data = response.json()
        
        if 'c' in data and 'pc' in data:
            current_price = data['c']
            previous_close = data['pc']
            return current_price, previous_close
        else:
            print(f"获取 {symbol} 数据失败: API返回数据不完整")
            return None, None
            
    except requests.exceptions.Timeout:
        print(f"获取 {symbol} 数据超时，跳过")
        return None, None
    except Exception as e:
        print(f"获取 {symbol} 数据时发生错误: {e}")
        return None, None

def send_alert_email(symbol, current_price, previous_close, drop_pct):
    """发送警报邮件"""
    subject = f"【股价下跌警报】{symbol} 跌幅达{drop_pct:.2f}%"
    
    body = f"""
    监控时间: {datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')}
    
    公司代码: {symbol}
    当前价格: ${current_price:.2f}
    前收盘价: ${previous_close:.2f}
    日内跌幅: {drop_pct:.2f}%
    
    此邮件由股票监控系统自动发送，请勿直接回复。
    """
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = Header(SENDER_EMAIL, 'utf-8')
    # 邮件头To字段可以只写第一个邮箱，或者用逗号分隔全部
    msg['To'] = Header(','.join(RECEIVER_EMAILS), 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    
    try:
        # 关键修改：为邮件发送也设置超时
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        server.quit()
        print(f"警报邮件发送成功: {symbol}")
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

def check_all_stocks():
    """检查所有股票的价格 - 这是主要的监控逻辑"""
    beijing_time = datetime.now(pytz.timezone('Asia/Shanghai'))
    print(f"{beijing_time.strftime('%Y-%m-%d %H:%M:%S')}: 开始执行监控任务...")
    
    alert_count = 0
    
    for symbol in STOCK_SYMBOLS:
        current_price, previous_close = get_stock_quote(symbol)
        
        if current_price is None or previous_close is None:
            print(f"跳过 {symbol}, 数据获取失败")
            continue
            
        if previous_close == 0:
            print(f"跳过 {symbol}, 前收盘价为0")
            continue
        
        daily_change_pct = ((current_price - previous_close) / previous_close) * 100
        
        if daily_change_pct <= DROP_THRESHOLD:
            print(f"警报! {symbol} 跌幅{daily_change_pct:.2f}%, 已触发警报阈值")
            success = send_alert_email(symbol, current_price, previous_close, daily_change_pct)
            if success:
                alert_count += 1
        else:
            print(f"{symbol}: 当前跌幅 {daily_change_pct:.2f}%, 未达警报线")
    
    print(f"本轮检查完成. 共触发 {alert_count} 次警报.\n")
    return alert_count

def main():
    """主函数"""
    # 检查必要环境变量是否设置
    if not all([FINNHUB_API_KEY, SENDER_EMAIL, SENDER_PASSWORD]) or not RECEIVER_EMAILS:
        print("错误: 缺少必要的环境变量配置!")
        print("请设置以下环境变量:")
        print(" - FINNHUB_API_KEY: Finnhub API密钥")
        print(" - SENDER_EMAIL: 发件邮箱地址")
        print(" - SENDER_PASSWORD: 邮箱应用专用密码")
        print(" - RECEIVER_EMAIL: 接收警报的邮箱地址（多个邮箱用逗号,分隔）")
        return False
    
    print("美股监控程序开始执行...")
    print(f"监控股票数量: {len(STOCK_SYMBOLS)}")
    print(f"跌幅阈值: {DROP_THRESHOLD}%")
    print(f"收件人列表: {RECEIVER_EMAILS}")
    print("=" * 50)
    
    start_time = time.time()
    alert_count = check_all_stocks()
    end_time = time.time()
    
    print(f"程序执行完成，耗时: {end_time - start_time:.2f} 秒")
    print(f"本次运行共发送 {alert_count} 条警报邮件")
    return True

# 关键修改：移除了 schedule 库的导入和使用，因为 GitHub Actions 的定时由工作流控制
if __name__ == "__main__":
    # 这个脚本现在会在每次被调用时执行一次完整的监控，然后正常退出
    success = main()

    exit(0 if success else 1)

import requests
import schedule
import time
import smtplib
import os  # 新增：用于读取环境变量
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
import pytz

# -------------------------------- 配置区域 -----------------------------------
# 所有敏感信息现在从环境变量读取 [5,8](@ref)
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')  # 从环境变量读取API密钥
SMTP_SERVER = os.getenv('SMTP_SERVER', "smtp-mail.outlook.com")  # 提供默认值
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))  # 端口转换为整数
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')

# 监控参数
DROP_THRESHOLD = -5.0  # 跌幅阈值 (-5%)

# 要监控的50家公司的股票代码列表
STOCK_SYMBOLS = ['JPM', 'ORCL', 'LLY', 'NFLX', 'ABBV', 'IBKR', 'AMD', 'CRM', 'MS', 'GS',
                 'MRK', 'MU', 'DIS', 'APP', 'NOW', 'LRCX', 'ANET', 'INTU', 'BLK', 'QCOM',
                 'AMAT', 'INTC', 'SCHW', 'TXN', 'ISRG', 'PFE', 'KLAC', 'ADBE', 'CRWD', 'ADI',
                 'KKR', 'COIN', 'NEM', 'BMY', 'RBLX', 'SNOW', 'CVNA', 'EQIX', 'NET', 'MRVL',
                 'CRWV', 'MNST', 'VRT', 'EXC', 'ETR', 'EA', 'ZS', 'XEL', 'CVS', 'WDC']
# ---------------------------------------------------------------------------

def get_stock_quote(symbol):
    """从Finnhub API获取股票实时报价和前收盘价"""
    # 为网络请求添加超时参数，防止挂起 [4](@ref)
    timeout_duration = (10, 30)  # 10秒连接超时，30秒读取超时
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=timeout_duration)
        data = response.json()
        
        if 'c' in data and 'pc' in data:
            current_price = data['c']
            previous_close = data['pc']
            return current_price, previous_close
        else:
            print(f"获取 {symbol} 数据失败: API返回数据不完整")
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
    msg['To'] = Header(RECEIVER_EMAIL, 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        server.quit()
        print(f"警报邮件发送成功: {symbol}")
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

def check_all_stocks():
    """检查所有股票的价格"""
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

def main():
    """主函数，设置定时任务"""
    # 检查必要环境变量是否设置 [8](@ref)
    if not all([FINNHUB_API_KEY, SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL]):
        print("错误: 缺少必要的环境变量配置!")
        print("请设置以下环境变量:")
        print(" - FINNHUB_API_KEY: Finnhub API密钥")
        print(" - SENDER_EMAIL: 发件邮箱地址")
        print(" - SENDER_PASSWORD: 邮箱应用专用密码")
        print(" - RECEIVER_EMAIL: 接收警报的邮箱地址")
        return
    
    schedule.every().day.at("23:30").do(check_all_stocks)  # UTC时间23:30对应北京时间7:30
    schedule.every().day.at("15:00").do(check_all_stocks)  # UTC时间15:00对应北京时间23:00
    
    print("美股监控程序已启动...")
    print(f"监控股票数量: {len(STOCK_SYMBOLS)}")
    print(f"跌幅阈值: {DROP_THRESHOLD}%")
    print("监控时间: UTC时间15:00和23:30 (对应北京时间23:00和7:30)")
    print("程序运行中，等待定时触发...\n")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
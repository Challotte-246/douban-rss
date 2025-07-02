import requests
from bs4 import BeautifulSoup
import datetime
import time
import re
import os
import random
import xml.etree.ElementTree as ET

# ===== 配置区域 =====
GROUP_ID = "713925"  # 豆瓣小组ID
RETRY_COUNT = 3      # 请求失败重试次数
DEBUG_MODE = True    # 启用详细日志输出

# 用户代理列表（随机选择防止封禁）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
]

# ===== 辅助函数 =====
def get_random_user_agent():
    return random.choice(USER_AGENTS)

def safe_request(url, headers, retry=RETRY_COUNT):
    for attempt in range(retry):
        try:
            print(f"📡 尝试请求: {url} (第 {attempt+1}/{retry} 次尝试)")
            delay = random.uniform(1.0, 3.0)
            time.sleep(delay)
            
            response = requests.get(url, headers=headers, timeout=15)
            print(f"🔄 HTTP 状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ 请求成功!")
                return response
                
            print(f"⚠️ 请求失败: HTTP {response.status_code}, 第 {attempt+1} 次重试...")
            
        except requests.exceptions.Timeout:
            print(f"⏱️ 请求超时, 第 {attempt+1} 次重试...")
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求异常: {str(e)}, 第 {attempt+1} 次重试...")
        
        sleep_time = 2 ** (attempt + 1)
        print(f"💤 等待 {sleep_time} 秒后重试...")
        time.sleep(sleep_time)
    
    raise Exception(f"🚫 多次请求失败: {url}")

def parse_douban_time(time_str):
    now = datetime.datetime.now()
    print(f"⏰ 原始时间字符串: '{time_str}'")
    
    try:
        if ':' in time_str and len(time_str) <= 5:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return datetime.datetime(now.year, now.month, now.day, hour, minute)
        
        elif re.match(r'^\d{1,2}-\d{1,2}$', time_str):
            parts = time_str.split('-')
            month = int(parts[0])
            day = int(parts[1])
            return datetime.datetime(now.year, month, day)
        
        elif re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', time_str):
            return datetime.datetime.strptime(time_str, "%Y-%m-%d")
        
        elif "昨天" in time_str:
            time_part = time_str.replace("昨天", "").strip()
            if ':' in time_part:
                parts = time_part.split(':')
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
            else:
                hour, minute = 0, 0
            yesterday = now - datetime.timedelta(days=1)
            return datetime.datetime(yesterday.year, yesterday.month, yesterday.day, hour, minute)
            
    except Exception as e:
        print(f"❌ 时间解析错误: {str(e)}")
    
    print(f"⚠️ 无法解析的时间格式: '{time_str}'，使用当前时间代替")
    return now

# ===== 主功能函数 =====
def fetch_group_posts():
    print(f"\n🔍 开始抓取小组 {GROUP_ID} 的讨论页面...")
    
    url = f"https://www.douban.com/group/{GROUP_ID}/discussion"
    user_agent = get_random_user_agent()
    headers = {
        "User-Agent": user_agent,
        "Referer": f"https://www.douban.com/group/{GROUP_ID}/",
    }
    
    print(f"🌐 目标URL: {url}")
    print(f"🧪 使用User-Agent: {user_agent}")
    
    try:
        response = safe_request(url, headers)
    except Exception as e:
        print(f"🔥 抓取失败: {str(e)}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    post_table = soup.select_one('table.olt')
    if not post_table:
        print("⚠️ 警告: 未找到帖子表格 (table.olt)")
        return []
    
    posts = []
    for row in post_table.select('tr')[1:]:
        title_cell = row.select_one('td.title')
        if not title_cell: continue
            
        title_link = title_cell.find('a')
        if not title_link: continue
            
        title = title_link.get_text(strip=True)
        link = title_link.get('href', '')
        
        time_cell = row.select_one('td.time')
        time_str = time_cell.get_text(strip=True) if time_cell else "未知时间"
        
        try:
            post_time = parse_douban_time(time_str)
        except:
            post_time = datetime.datetime.now()
            
        posts.append({
            "title": title,
            "link": link,
            "pubDate": post_time,
            "raw_time": time_str
        })
    
    print(f"✅ 成功抓取 {len(posts)} 条帖子")
    return sorted(posts, key=lambda x: x["pubDate"], reverse=True)

def generate_rss(posts):
    """手动生成RSS XML"""
    # 创建RSS根元素
    rss = ET.Element('rss', version='2.0')
    
    # 创建频道
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = f"豆瓣小组 {GROUP_ID} 更新"
    ET.SubElement(channel, 'link').text = f"https://www.douban.com/group/{GROUP_ID}"
    ET.SubElement(channel, 'description').text = "自动抓取的小组更新"
    ET.SubElement(channel, 'language').text = "zh-cn"
    
    # 添加帖子项
    for post in posts:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = post['title']
        ET.SubElement(item, 'link').text = post['link']
        ET.SubElement(item, 'pubDate').text = post['pubDate'].strftime('%a, %d %b %Y %H:%M:%S GMT')
        ET.SubElement(item, 'description').text = f"发布于: {post['raw_time']}"
    
    # 生成XML字符串
    return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(rss, encoding='unicode')

# ===== 主程序 =====
if __name__ == "__main__":
    print("=" * 60)
    print(f"🚀 豆瓣小组 RSS 生成器启动 - 小组ID: {GROUP_ID}")
    print(f"⏱️ 开始时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        posts = fetch_group_posts()
        
        if posts:
            print("\n📢 最新3条帖子:")
            for i, post in enumerate(posts[:3]):
                print(f"  {i+1}. [{post['raw_time']}] {post['title']}")
        
        rss_xml = generate_rss(posts)
        
        filename = f"douban_{GROUP_ID}.xml"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(rss_xml)
        
        print(f"\n🎉 RSS文件已生成: {filename}")
        print(f"📊 包含 {len(posts)} 条帖子")
        
    except Exception as e:
        print(f"\n🔥 严重错误: {str(e)}")
        print("🆘 创建空RSS文件...")
        
        filename = f"douban_{GROUP_ID}.xml"
        with open(filename, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write('<rss version="2.0">\n')
            f.write('<channel>\n')
            f.write(f'<title>豆瓣小组 {GROUP_ID} 更新</title>\n')
            f.write('<description>抓取失败，请检查日志</description>\n')
            f.write('</channel>\n')
            f.write('</rss>')
        
        print(f"📁 已创建空文件: {filename}")
    
    print("\n🏁 任务完成!")

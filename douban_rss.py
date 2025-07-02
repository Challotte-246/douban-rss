import requests
from bs4 import BeautifulSoup
import datetime
import time
import re
import os
import random
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

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
            if DEBUG_MODE:
                print(f"📡 尝试请求: {url} (第 {attempt+1}/{retry} 次尝试)")
            delay = random.uniform(1.0, 3.0)
            time.sleep(delay)
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if DEBUG_MODE:
                print(f"🔄 HTTP 状态码: {response.status_code}")
            
            if response.status_code == 200:
                if DEBUG_MODE:
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
    
    if DEBUG_MODE:
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

# ===== 主抓取函数 =====
def fetch_discussion_posts():
    """抓取讨论区帖子（包含最新和最热）"""
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
        response.encoding = 'utf-8'
    except Exception as e:
        print(f"🔥 抓取失败: {str(e)}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 查找帖子容器
    post_table = soup.select_one('table.olt')
    if not post_table:
        print("⚠️ 警告: 未找到帖子表格")
        return []
    
    posts = []
    for row in post_table.select('tr')[1:]:
        title_cell = row.select_one('td.title')
        if not title_cell: continue
            
        title_link = title_cell.find('a')
        if not title_link: continue
            
        # 提取标题和链接
        title = title_link.get_text(strip=True)
        link = title_link.get('href', '')
        
        # 提取回复数
        reply_cell = row.select_one('td.r-count')
        reply_count = int(reply_cell.get_text(strip=True)) if reply_cell else 0
        
        # 提取时间
        time_cell = row.select_one('td.time')
        time_str = time_cell.get_text(strip=True) if time_cell else "未知时间"
        
        try:
            post_time = parse_douban_time(time_str)
        except:
            post_time = datetime.datetime.now()
            
        # 提取分类标签（如[讨论]、[转让]等）
        category = ""
        if title.startswith('[') and ']' in title:
            end_index = title.find(']') + 1
            category = title[:end_index]
            title = title[end_index:].strip()
        
        posts.append({
            "title": title,
            "link": link,
            "pubDate": post_time,
            "raw_time": time_str,
            "reply_count": reply_count,
            "category": category
        })
    
    print(f"✅ 成功抓取 {len(posts)} 条讨论区帖子")
    
    # 返回原始帖子列表（用于后续排序）
    return posts

def fetch_elite_posts():
    """抓取精华区帖子"""
    print(f"\n🔍 开始抓取小组 {GROUP_ID} 的精华区...")
    
    url = f"https://www.douban.com/group/{GROUP_ID}/discussion?type=elite"
    user_agent = get_random_user_agent()
    headers = {
        "User-Agent": user_agent,
        "Referer": f"https://www.douban.com/group/{GROUP_ID}/",
    }
    
    print(f"🌐 目标URL: {url}")
    print(f"🧪 使用User-Agent: {user_agent}")
    
    try:
        response = safe_request(url, headers)
        response.encoding = 'utf-8'
    except Exception as e:
        print(f"🔥 抓取失败: {str(e)}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 查找精华区帖子容器
    elite_posts = []
    topic_items = soup.select('div.topic-item')
    
    if not topic_items:
        print("⚠️ 警告: 未找到精华区帖子")
        return []
    
    for item in topic_items:
        # 提取标题和链接
        title_link = item.select_one('div.title a')
        if not title_link: continue
            
        title = title_link.get_text(strip=True)
        link = title_link.get('href', '')
        
        # 提取作者
        author_elem = item.select_one('span.author a')
        author = author_elem.get_text(strip=True) if author_elem else "未知作者"
        
        # 提取回复数和收藏数
        stats = item.select_one('span.stats')
        reply_count = 0
        if stats:
            # 提取格式如："12回复 45收藏"
            match = re.search(r'(\d+)回复', stats.get_text())
            if match:
                reply_count = int(match.group(1))
        
        # 提取时间
        time_elem = item.select_one('span.time')
        time_str = time_elem.get_text(strip=True) if time_elem else "未知时间"
        
        try:
            post_time = parse_douban_time(time_str)
        except:
            post_time = datetime.datetime.now()
            
        # 提取分类标签
        category = ""
        if title.startswith('[') and ']' in title:
            end_index = title.find(']') + 1
            category = title[:end_index]
            title = title[end_index:].strip()
        
        elite_posts.append({
            "title": title,
            "link": link,
            "pubDate": post_time,
            "raw_time": time_str,
            "reply_count": reply_count,
            "author": author,
            "category": category,
            "is_elite": True  # 标记为精华帖
        })
    
    print(f"✅ 成功抓取 {len(elite_posts)} 条精华帖")
    return elite_posts

# ===== RSS生成函数 =====
def generate_rss(posts, feed_type="new"):
    """生成RSS XML
    
    feed_type: 
        'new' - 最新帖子
        'hot' - 热门帖子
        'elite' - 精华帖子
    """
    # 设置标题和描述
    titles = {
        "new": f"豆瓣小组 {GROUP_ID} 最新更新",
        "hot": f"豆瓣小组 {GROUP_ID} 热门帖子",
        "elite": f"豆瓣小组 {GROUP_ID} 精华推荐"
    }
    
    descriptions = {
        "new": "按发布时间排序的最新小组讨论",
        "hot": "按回复数排序的热门小组讨论",
        "elite": "豆瓣小组精华帖精选"
    }
    
    # 创建RSS根元素
    rss = ET.Element('rss', version='2.0')
    
    # 创建频道
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = titles[feed_type]
    ET.SubElement(channel, 'link').text = f"https://www.douban.com/group/{GROUP_ID}"
    ET.SubElement(channel, 'description').text = descriptions[feed_type]
    ET.SubElement(channel, 'language').text = "zh-cn"
    
    # 添加帖子项（带排名）
    for index, post in enumerate(posts):
        # 根据类型添加不同的标题前缀
        if feed_type == "elite":
            title_prefix = f"🔥 精华 #{index+1}: "
        elif feed_type == "hot":
            title_prefix = f"🔥 热门 #{index+1}: "
        else:
            title_prefix = f"🆕 最新 #{index+1}: "
        
        # 添加分类标签
        if post.get("category"):
            title_prefix = post["category"] + " " + title_prefix
        
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = title_prefix + post['title']
        ET.SubElement(item, 'link').text = post['link']
        ET.SubElement(item, 'pubDate').text = post['pubDate'].strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        # 构建详细描述
        description = f"发布于: {post['raw_time']}"
        if post.get("reply_count", 0) > 0:
            description += f" | 回复数: {post['reply_count']}"
        if post.get("author"):
            description += f" | 作者: {post['author']}"
        if post.get("is_elite"):
            description += " | 🔥精华帖"
        
        ET.SubElement(item, 'description').text = description
    
    # 生成XML字符串
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(rss, encoding='unicode')

# ===== 主程序 =====
if __name__ == "__main__":
    print("=" * 60)
    print(f"🚀 豆瓣小组 RSS 生成器启动 - 小组ID: {GROUP_ID}")
    print(f"⏱️ 开始时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # 抓取讨论区帖子
        discussion_posts = fetch_discussion_posts()
        
        # 抓取精华区帖子
        elite_posts = fetch_elite_posts()
        
        # 生成三种排序的帖子列表
        new_posts = sorted(discussion_posts, key=lambda x: x["pubDate"], reverse=True)[:50]  # 最新50条
        hot_posts = sorted(discussion_posts, key=lambda x: x["reply_count"], reverse=True)[:50]  # 最热50条
        
        # 生成三个RSS源
        rss_new = generate_rss(new_posts, "new")
        rss_hot = generate_rss(hot_posts, "hot")
        rss_elite = generate_rss(elite_posts, "elite")
        
        # 保存到文件
        with open(f"douban_{GROUP_ID}_new.xml", "w", encoding="utf-8") as f:
            f.write(rss_new)
        
        with open(f"douban_{GROUP_ID}_hot.xml", "w", encoding="utf-8") as f:
            f.write(rss_hot)
        
        with open(f"douban_{GROUP_ID}_elite.xml", "w", encoding="utf-8") as f:
            f.write(rss_elite)
        
        print("\n🎉 RSS文件已生成:")
        print(f"📰 最新帖: douban_{GROUP_ID}_new.xml ({len(new_posts)}条)")
        print(f"🔥 热门帖: douban_{GROUP_ID}_hot.xml ({len(hot_posts)}条)")
        print(f"🌟 精华帖: douban_{GROUP_ID}_elite.xml ({len(elite_posts)}条)")
        
        # 显示示例
        if new_posts:
            print("\n📢 最新帖示例:")
            for i, post in enumerate(new_posts[:3]):
                print(f"  {i+1}. [{post['raw_time']}] {post['category']}{post['title']}")
        
        if hot_posts:
            print("\n🔥 热门帖示例:")
            for i, post in enumerate(hot_posts[:3]):
                print(f"  {i+1}. [{post['reply_count']}回复] {post['category']}{post['title']}")
        
        if elite_posts:
            print("\n🌟 精华帖示例:")
            for i, post in enumerate(elite_posts[:3]):
                print(f"  {i+1}. [{post['author']}] {post['category']}{post['title']}")
        
    except Exception as e:
        print(f"\n🔥 严重错误: {str(e)}")
        print("🆘 创建空RSS文件...")
        
        # 创建三个空文件防止工作流失败
        for feed_type in ["new", "hot", "elite"]:
            filename = f"douban_{GROUP_ID}_{feed_type}.xml"
            with open(filename, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                f.write('<rss version="2.0">\n')
                f.write('<channel>\n')
                f.write(f'<title>豆瓣小组 {GROUP_ID} {"最新" if feed_type=="new" else "热门" if feed_type=="hot" else "精华"}帖</title>\n')
                f.write('<description>抓取失败，请检查日志</description>\n')
                f.write('</channel>\n')
                f.write('</rss>')
            print(f"📁 已创建空文件: {filename}")
    
    print("\n🏁 任务完成!")

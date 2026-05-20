# -*- coding: utf-8 -*-
"""
爬虫调试测试脚本
用于测试和调试微博爬虫的各个模块，包括文本、图片、视频的获取
"""

import os
import sys
import re
import json
import time
import requests

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from bs4 import BeautifulSoup

from crawler_wb.config import load_config, get_absolute_path
from crawler_wb.cookie_manager import CookieManager
from crawler_wb.data_extractor import WeiboExtractor
from crawler_wb.data_cleaner import DataCleaner
from crawler_wb.utils import (
    build_search_url,
    get_request_headers,
    save_json,
    ensure_dir,
    get_random_user_agent,
)


class CrawlerTester:
    """爬虫测试器"""

    def __init__(self):
        """初始化测试器"""
        self.config = load_config()
        self.cookie_manager = CookieManager(
            cookie_file=get_absolute_path(self.config.cookie_file),
            max_fail_count=self.config.cookie_manager.max_fail_count
        )
        self.extractor = WeiboExtractor(timeout=30)
        self.cleaner = DataCleaner()

        # 测试输出目录
        self.test_output_dir = get_absolute_path("logs/test_output")
        self.test_images_dir = get_absolute_path("logs/test_output/images")
        self.test_videos_dir = get_absolute_path("logs/test_output/videos")
        ensure_dir(self.test_output_dir)
        ensure_dir(self.test_images_dir)
        ensure_dir(self.test_videos_dir)

        self.cookie = None
        self.test_html = None

    def print_separator(self, title: str):
        """打印分隔线"""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)

    def print_modality_config(self):
        """打印模态数据配置"""
        print("\n模态数据保存配置:")
        print(f"  保存文本: {self.config.modalities.save_text}")
        print(f"  保存图片: {self.config.modalities.save_images}")
        print(f"  保存视频: {self.config.modalities.save_videos}")
        print(f"  图片质量: {self.config.modalities.image_quality}")
        print(f"  视频质量: {self.config.modalities.video_quality}")

    def test_cookie_loading(self) -> bool:
        """测试Cookie加载"""
        self.print_separator("测试1: Cookie加载")

        print(f"Cookie文件: {get_absolute_path(self.config.cookie_file)}")
        print(f"总Cookie数: {self.cookie_manager.get_total_count()}")
        print(f"有效Cookie数: {self.cookie_manager.get_valid_count()}")

        self.cookie = self.cookie_manager.get_cookie()
        if self.cookie:
            print(f"\nCookie前80字符: {self.cookie[:80]}...")
            print("✓ Cookie加载成功!")
            return True
        else:
            print("✗ Cookie加载失败!")
            return False

    def test_page_fetch(self) -> bool:
        """测试页面获取"""
        self.print_separator("测试2: 页面获取")

        keyword = "洪灾"
        start_time = datetime(2024, 6, 13, 8, 0)
        end_time = datetime(2024, 6, 13, 12, 0)
        url = build_search_url(keyword, start_time, end_time, page=1)

        print(f"搜索关键词: {keyword}")
        print(f"时间范围: {start_time} - {end_time}")
        print(f"请求URL: {url}")

        print(f"\n正在获取页面...")
        self.test_html = self.extractor.fetch_page(url, self.cookie)

        if self.test_html:
            print(f"✓ 页面获取成功! 内容长度: {len(self.test_html)} 字符")

            debug_file = os.path.join(self.test_output_dir, "debug_page.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(self.test_html)
            print(f"HTML已保存到: {debug_file}")

            return True
        else:
            print("✗ 页面获取失败!")
            return False

    def test_data_extraction(self) -> list:
        """测试数据提取"""
        self.print_separator("测试3: 数据提取")

        if not self.test_html:
            print("✗ 没有HTML内容可提取")
            return []

        weibos = self.extractor.extract_weibo_list(self.test_html)
        print(f"提取到的微博数: {len(weibos)}")

        if weibos:
            print("\n✓ 微博数据提取成功!")
            print("\n微博数据示例 (前3条):")
            for i, weibo in enumerate(weibos[:3]):
                print(f"\n--- 微博 {i+1} ---")
                print(f"  ID: {weibo.get('weibo_id')}")
                print(f"  作者: {weibo.get('author')}")
                print(f"  内容: {weibo.get('content', '')[:60]}...")
                print(f"  时间: {weibo.get('publish_time')}")
                print(f"  有图片: {weibo.get('has_images')}")
                print(f"  有视频: {weibo.get('has_video')}")

            output_file = os.path.join(self.test_output_dir, "extracted_weibos.json")
            save_json(weibos, output_file)
            print(f"\n提取数据已保存到: {output_file}")
        else:
            print("✗ 未能提取到微博数据")

        return weibos

    def test_media_download(self, weibos: list) -> dict:
        """测试媒体下载（图片和视频）"""
        self.print_separator("测试4: 媒体下载测试")

        results = {
            'images_downloaded': 0,
            'videos_downloaded': 0,
            'image_errors': [],
            'video_errors': [],
        }

        if not weibos:
            print("✗ 没有微博数据，跳过媒体下载测试")
            return results

        if not self.test_html:
            print("✗ 没有HTML内容")
            return results

        soup = BeautifulSoup(self.test_html, 'html.parser')

        # 找到所有微博卡片
        cards = soup.select('.card-wrap[action-type="feed_list_item"]')
        print(f"找到 {len(cards)} 个微博卡片")

        # 测试前3条有媒体的微博
        test_count = 0
        for card in cards:
            if test_count >= 3:
                break

            mid = card.get('mid', '')
            if not mid:
                continue

            print(f"\n--- 测试微博 {mid} ---")

            # 提取并下载视频
            video_urls = self._extract_video_urls(card)
            if video_urls:
                print(f"找到 {len(video_urls)} 个视频URL")
                for i, video_url in enumerate(video_urls[:1]):  # 只下载第一个
                    video_path = os.path.join(self.test_videos_dir, f"{mid}_video_{i}.mp4")
                    if self._download_file(video_url, video_path):
                        print(f"  ✓ 视频下载成功: {video_path}")
                        results['videos_downloaded'] += 1
                    else:
                        print(f"  ✗ 视频下载失败: {video_url[:50]}...")
                        results['video_errors'].append(video_url)

            # 提取并下载图片
            image_urls = self._extract_image_urls(card)
            if image_urls:
                print(f"找到 {len(image_urls)} 个图片URL")
                weibo_image_dir = os.path.join(self.test_images_dir, mid)
                ensure_dir(weibo_image_dir)

                for i, img_url in enumerate(image_urls[:3]):  # 只下载前3张
                    img_path = os.path.join(weibo_image_dir, f"{i}.jpg")
                    if self._download_file(img_url, img_path):
                        print(f"  ✓ 图片下载成功: {img_path}")
                        results['images_downloaded'] += 1
                    else:
                        print(f"  ✗ 图片下载失败: {img_url[:50]}...")
                        results['image_errors'].append(img_url)

            if video_urls or image_urls:
                test_count += 1

        return results

    def _extract_video_urls(self, card) -> list:
        """从卡片中提取视频URL"""
        video_urls = []

        # 方法1: 从data-str属性中提取
        video_elem = card.select_one('.WB_video_h5[data-str]')
        if video_elem:
            data_str = video_elem.get('data-str', '')
            # 提取视频URL
            url_matches = re.findall(r"src:\s*'([^']+\.mp4[^']*)'", data_str)
            for url in url_matches:
                if url.startswith('//'):
                    url = 'https:' + url
                video_urls.append(url)

        # 方法2: 从video标签提取
        video_tags = card.select('video source[src]')
        for tag in video_tags:
            src = tag.get('src', '')
            if src and '.mp4' in src:
                if src.startswith('//'):
                    src = 'https:' + src
                video_urls.append(src)

        return video_urls

    def _extract_image_urls(self, card) -> list:
        """从卡片中提取图片URL"""
        image_urls = []

        # 方法1: 从data-str属性中提取poster（封面图）
        video_elem = card.select_one('.WB_video_h5[data-str]')
        if video_elem:
            data_str = video_elem.get('data-str', '')
            poster_matches = re.findall(r"poster:\s*'([^']+sinaimg[^']+)'", data_str)
            for url in poster_matches:
                # 替换为高清版本
                url = re.sub(r'/orj\d+/', '/large/', url)
                image_urls.append(url)

        # 方法2: 从img标签提取
        img_tags = card.select('img[src*="sinaimg"]')
        for img in img_tags:
            src = img.get('src', '')
            if src and 'sinaimg' in src:
                # 替换为高清版本
                src = re.sub(r'/crop\.[^/]+/', '/large/', src)
                src = re.sub(r'/orj\d+/', '/large/', src)
                src = re.sub(r'/thumb\d+/', '/large/', src)
                if src not in image_urls:
                    image_urls.append(src)

        # 方法3: 从thumbnail中提取
        thumbnail = card.select_one('.thumbnail img')
        if thumbnail:
            src = thumbnail.get('src', '')
            if src and 'sinaimg' in src:
                src = re.sub(r'/orj\d+/', '/large/', src)
                if src not in image_urls:
                    image_urls.append(src)

        return image_urls

    def _download_file(self, url: str, filepath: str) -> bool:
        """下载文件"""
        try:
            headers = {
                'User-Agent': get_random_user_agent(),
                'Referer': 'https://weibo.com/',
            }

            response = requests.get(url, headers=headers, timeout=30, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
        except Exception as e:
            print(f"    下载错误: {e}")
        return False

    def test_full_pipeline(self) -> dict:
        """测试完整爬取流程"""
        self.print_separator("测试5: 完整爬取流程测试")

        keyword = "洪灾"
        start_time = datetime(2024, 6, 13, 10, 0)
        end_time = datetime(2024, 6, 13, 11, 0)

        print(f"关键词: {keyword}")
        print(f"时间窗口: {start_time} - {end_time}")

        url = build_search_url(keyword, start_time, end_time, page=1)
        print(f"URL: {url}")

        # 获取页面
        print("\n1. 获取页面...")
        html = self.extractor.fetch_page(url, self.cookie)
        if not html:
            print("✗ 页面获取失败")
            return {'success': False, 'error': '页面获取失败'}

        print(f"✓ 页面获取成功，长度: {len(html)}")

        # 提取数据
        print("\n2. 提取微博数据...")
        weibos = self.extractor.extract_weibo_list(html)
        print(f"提取到 {len(weibos)} 条微博")

        if not weibos:
            print("✗ 没有提取到数据")
            return {'success': False, 'error': '没有提取到数据'}

        # 清洗数据
        print("\n3. 清洗数据...")
        cleaned_weibos = []
        for weibo in weibos[:5]:
            cleaned = self.cleaner.clean_weibo_data(weibo)
            cleaned_weibos.append(cleaned)

        print(f"清洗完成，示例:")
        if cleaned_weibos:
            print(f"  作者: {cleaned_weibos[0].get('author')}")
            print(f"  内容: {cleaned_weibos[0].get('content', '')[:50]}...")

        # 保存数据
        print("\n4. 保存数据...")
        output_file = os.path.join(self.test_output_dir, "test_full_pipeline.json")
        save_json(cleaned_weibos, output_file)
        print(f"✓ 数据已保存到: {output_file}")

        return {
            'success': True,
            'weibo_count': len(weibos),
            'cleaned_count': len(cleaned_weibos),
            'output_file': output_file
        }

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "#"*60)
        print("# 微博爬虫完整功能测试")
        print("#"*60)

        # 打印模态配置
        self.print_modality_config()

        results = {}

        # 测试1: Cookie加载
        if not self.test_cookie_loading():
            print("\n❌ 测试终止: Cookie加载失败")
            return

        # 测试2: 页面获取
        if not self.test_page_fetch():
            print("\n❌ 测试终止: 页面获取失败")
            return

        # 测试3: 数据提取
        weibos = self.test_data_extraction()
        results['weibo_count'] = len(weibos)

        # 测试4: 媒体下载（根据配置决定是否执行）
        if self.config.modalities.save_images or self.config.modalities.save_videos:
            media_results = self.test_media_download(weibos)
            results['media'] = media_results
        else:
            print("\n⚠ 媒体下载已禁用（配置中 save_images=false, save_videos=false）")
            results['media'] = {'images_downloaded': 0, 'videos_downloaded': 0}

        # 测试5: 完整流程
        pipeline_results = self.test_full_pipeline()
        results['pipeline'] = pipeline_results

        # 打印总结
        self.print_summary(results)

    def print_summary(self, results: dict):
        """打印测试总结"""
        self.print_separator("测试总结")

        print(f"\n测试输出目录: {self.test_output_dir}")
        print("\n生成的文件:")
        for root, dirs, files in os.walk(self.test_output_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.test_output_dir)
                size = os.path.getsize(filepath)
                print(f"  - {rel_path} ({size:,} bytes)")

        print("\n测试结果:")
        print(f"  微博数量: {results.get('weibo_count', 0)}")
        print(f"  图片下载: {results.get('media', {}).get('images_downloaded', 0)} 成功")
        print(f"  视频下载: {results.get('media', {}).get('videos_downloaded', 0)} 成功")
        print(f"  完整流程: {'✓ 成功' if results.get('pipeline', {}).get('success') else '✗ 失败'}")

        print("\n" + "#"*60)
        print("# 测试完成")
        print("#"*60)


def main():
    """主函数"""
    tester = CrawlerTester()
    tester.run_all_tests()


if __name__ == '__main__':
    main()

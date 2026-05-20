# -*- coding: utf-8 -*-
"""
Cookie管理模块
从txt文件读取Cookie，管理Cookie轮换和失效检测
支持标记失效Cookie（添加【ERROR】前缀）而非直接删除
"""

import os
import time
import random
from typing import List, Optional
from dataclasses import dataclass


# 失效Cookie标记前缀
ERROR_PREFIX = "【ERROR】"


@dataclass
class CookieInfo:
    """Cookie信息"""
    value: str           # Cookie值（不含标记前缀）
    original_line: str   # 文件中的原始行内容
    is_valid: bool = True
    fail_count: int = 0
    last_used: float = 0
    use_count: int = 0


class CookieManager:
    """Cookie管理器"""

    def __init__(self, cookie_file: str, max_fail_count: int = 3):
        """
        初始化Cookie管理器

        Args:
            cookie_file: Cookie文件路径（每行一个Cookie）
            max_fail_count: 最大失败次数，超过后标记为失效
        """
        self.cookie_file = cookie_file
        self.max_fail_count = max_fail_count
        self.cookie_list: List[CookieInfo] = []

        # 从文件加载Cookie
        self._load_cookies_from_file()

    def _load_cookies_from_file(self) -> None:
        """从文件加载Cookie"""
        if not os.path.exists(self.cookie_file):
            print(f"Cookie文件不存在: {self.cookie_file}")
            print("请创建该文件并添加Cookie（每行一个）")
            return

        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line in lines:
                original_line = line.strip()
                if not original_line:
                    continue  # 忽略空行

                # 检查是否是注释行
                if original_line.startswith('#'):
                    continue  # 忽略注释

                # 检查是否已被标记为失效
                if original_line.startswith(ERROR_PREFIX):
                    # 提取Cookie值（去除标记前缀）
                    cookie_value = original_line[len(ERROR_PREFIX):].strip()
                    if cookie_value:
                        # 加载但标记为无效
                        cookie_info = CookieInfo(
                            value=cookie_value,
                            original_line=original_line,
                            is_valid=False,
                            fail_count=self.max_fail_count  # 已失效
                        )
                        self.cookie_list.append(cookie_info)
                else:
                    # 正常Cookie
                    self.cookie_list.append(CookieInfo(
                        value=original_line,
                        original_line=original_line,
                        is_valid=True
                    ))

            valid_count = sum(1 for c in self.cookie_list if c.is_valid)
            print(f"从文件加载了 {len(self.cookie_list)} 个Cookie（有效: {valid_count}，失效: {len(self.cookie_list) - valid_count}）")

        except Exception as e:
            print(f"读取Cookie文件失败: {e}")

    def _save_cookies_to_file(self) -> bool:
        """
        保存Cookie到文件，失效的Cookie添加【ERROR】标记

        Returns:
            是否保存成功
        """
        try:
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                f.write("# 微博Cookie列表（每行一个Cookie）\n")
                f.write("# 获取方法：登录weibo.com后从浏览器开发者工具中复制\n")
                f.write("# 失效Cookie会自动添加【ERROR】标记，可手动删除或更新\n\n")

                for cookie_info in self.cookie_list:
                    if cookie_info.is_valid:
                        # 有效Cookie，直接写入
                        f.write(f"{cookie_info.value}\n")
                    else:
                        # 失效Cookie，添加标记前缀
                        f.write(f"{ERROR_PREFIX}{cookie_info.value}\n")

            return True

        except Exception as e:
            print(f"保存Cookie文件失败: {e}")
            return False

    def get_cookie(self) -> Optional[str]:
        """
        随机获取一个有效的Cookie

        Returns:
            Cookie字符串，如果没有有效Cookie则返回None
        """
        valid_cookies = [c for c in self.cookie_list if c.is_valid]

        if not valid_cookies:
            print("没有有效的Cookie可用！")
            print("请检查cookies_wb.txt文件，更新或删除带有【ERROR】标记的Cookie")
            return None

        # 随机选择一个有效的Cookie
        cookie_info = random.choice(valid_cookies)
        cookie_info.last_used = time.time()
        cookie_info.use_count += 1

        return cookie_info.value

    def report_success(self, cookie: str) -> None:
        """
        报告Cookie使用成功，重置失败计数

        Args:
            cookie: 成功使用的Cookie
        """
        for cookie_info in self.cookie_list:
            if cookie_info.value == cookie:
                cookie_info.fail_count = 0
                cookie_info.is_valid = True
                break

    def report_failure(self, cookie: str) -> bool:
        """
        报告Cookie使用失败
        如果失败次数超过阈值，则标记为失效（添加【ERROR】前缀）

        Args:
            cookie: 失败的Cookie

        Returns:
            Cookie是否被标记为失效
        """
        for cookie_info in self.cookie_list:
            if cookie_info.value == cookie:
                cookie_info.fail_count += 1
                print(f"Cookie失败次数: {cookie_info.fail_count}/{self.max_fail_count}")

                if cookie_info.fail_count >= self.max_fail_count:
                    # 标记为无效
                    cookie_info.is_valid = False
                    print(f"Cookie已失效，正在标记...")

                    # 更新文件（添加【ERROR】标记）
                    self._save_cookies_to_file()

                    valid_count = sum(1 for c in self.cookie_list if c.is_valid)
                    print(f"已标记失效Cookie，剩余有效Cookie: {valid_count} 个")

                    return True
                break

        return False

    def get_valid_count(self) -> int:
        """
        获取有效Cookie数量

        Returns:
            有效Cookie数量
        """
        return sum(1 for c in self.cookie_list if c.is_valid)

    def get_total_count(self) -> int:
        """
        获取总Cookie数量

        Returns:
            总Cookie数量
        """
        return len(self.cookie_list)

    def get_status(self) -> dict:
        """
        获取Cookie状态信息

        Returns:
            状态字典
        """
        return {
            "total": self.get_total_count(),
            "valid": self.get_valid_count(),
            "invalid": self.get_total_count() - self.get_valid_count(),
            "cookies": [
                {
                    "index": i,
                    "is_valid": c.is_valid,
                    "fail_count": c.fail_count,
                    "use_count": c.use_count,
                    "marked_error": not c.is_valid  # 是否已被标记为失效
                }
                for i, c in enumerate(self.cookie_list)
            ]
        }

    def add_cookie(self, cookie: str, save_to_file: bool = True) -> None:
        """
        添加新的Cookie

        Args:
            cookie: 新的Cookie字符串
            save_to_file: 是否同时保存到文件
        """
        if cookie and cookie.strip():
            cookie_value = cookie.strip()
            # 如果带有ERROR标记，去除它
            if cookie_value.startswith(ERROR_PREFIX):
                cookie_value = cookie_value[len(ERROR_PREFIX):].strip()

            new_cookie = CookieInfo(
                value=cookie_value,
                original_line=cookie_value,
                is_valid=True
            )
            self.cookie_list.append(new_cookie)

            if save_to_file:
                self._save_cookies_to_file()

    def remove_error_mark(self, cookie: str) -> bool:
        """
        移除Cookie的失效标记，重新启用

        Args:
            cookie: Cookie字符串

        Returns:
            是否成功移除标记
        """
        for cookie_info in self.cookie_list:
            if cookie_info.value == cookie and not cookie_info.is_valid:
                cookie_info.is_valid = True
                cookie_info.fail_count = 0
                self._save_cookies_to_file()
                print(f"已重新启用Cookie")
                return True
        return False

    def reload_from_file(self) -> None:
        """重新从文件加载Cookie"""
        self.cookie_list.clear()
        self._load_cookies_from_file()
"""
POCO 扫描器 & 提取器 & 动态占位符单元测试。
"""

import sys
import os
import random
import unittest

# 确保能导入 poco
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poco.scanner import read_docx_text
from poco.extractor import extract_placeholders
from poco.dynamic import (
    is_dynamic,
    generate,
    generate_value_if_dynamic,
    register,
    unregister,
)
from poco import scan_template, generate_mapping


class TestExtractor(unittest.TestCase):
    """占位符提取器测试"""

    def test_simple_placeholder(self):
        result = extract_placeholders("你好 {{姓名}}，欢迎。")
        self.assertEqual(result, ["姓名"])

    def test_multiple_placeholders(self):
        text = "{{姓名}} {{护照号}} {{出生日期}}"
        result = extract_placeholders(text)
        self.assertEqual(result, ["姓名", "护照号", "出生日期"])

    def test_deduplication(self):
        text = "{{姓名}} 和 {{姓名}} 和 {{护照号}}"
        result = extract_placeholders(text)
        self.assertEqual(result, ["姓名", "护照号"])

    def test_no_placeholders(self):
        result = extract_placeholders("普通文本，没有占位符。")
        self.assertEqual(result, [])

    def test_whitespace_trim(self):
        result = extract_placeholders("{{   姓名   }}")
        self.assertEqual(result, ["姓名"])

    def test_dynamic_placeholders(self):
        text = "编号：{{随机四位数}}，日期：{{当前日期}}"
        result = extract_placeholders(text)
        self.assertEqual(result, ["随机四位数", "当前日期"])

    def test_empty_braces(self):
        result = extract_placeholders("{{}}")
        self.assertEqual(result, [])


class TestDynamic(unittest.TestCase):
    """动态占位符测试"""

    def test_is_dynamic_builtin(self):
        self.assertTrue(is_dynamic("随机四位数"))
        self.assertTrue(is_dynamic("随机六位数"))
        self.assertTrue(is_dynamic("当前日期"))
        self.assertTrue(is_dynamic("当前时间"))

    def test_is_not_dynamic(self):
        self.assertFalse(is_dynamic("姓名"))
        self.assertFalse(is_dynamic("护照号"))
        self.assertFalse(is_dynamic(""))

    def test_random_four_digits(self):
        for _ in range(20):
            val = generate("随机四位数")
            self.assertEqual(len(val), 4)
            self.assertTrue(1000 <= int(val) <= 9999)

    def test_random_six_digits(self):
        for _ in range(20):
            val = generate("随机六位数")
            self.assertEqual(len(val), 6)
            self.assertTrue(100000 <= int(val) <= 999999)

    def test_current_date_format(self):
        val = generate("当前日期")
        parts = val.split("-")
        self.assertEqual(len(parts), 3)  # YYYY-MM-DD
        self.assertEqual(len(parts[0]), 4)

    def test_current_time_format(self):
        val = generate("当前时间")
        parts = val.split(":")
        self.assertEqual(len(parts), 2)  # HH:MM

    def test_generate_unknown_returns_empty(self):
        self.assertEqual(generate("姓名"), "")

    def test_generate_value_if_dynamic(self):
        self.assertIsNotNone(generate_value_if_dynamic("当前日期"))
        self.assertIsNone(generate_value_if_dynamic("姓名"))

    def test_custom_dynamic_register(self):
        register("自定义字段", lambda: "hello")
        self.assertTrue(is_dynamic("自定义字段"))
        self.assertEqual(generate("自定义字段"), "hello")
        unregister("自定义字段")
        self.assertFalse(is_dynamic("自定义字段"))


class TestScannerOnRealTemplates(unittest.TestCase):
    """使用真实模板文件进行集成测试"""

    @classmethod
    def setUpClass(cls):
        cls.mould_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "moulds",
        )

    def test_service_voucher_has_placeholders(self):
        path = os.path.join(self.mould_dir, "Service Voucher-MOULD.docx")
        if not os.path.exists(path):
            self.skipTest("模板文件不存在")
        placeholders = scan_template(path)
        self.assertGreater(len(placeholders), 0)
        # 应当包含月份相关占位符
        print(f"\n  Service Voucher placeholders: {placeholders}")

    def test_return_ticket_has_placeholders(self):
        path = os.path.join(self.mould_dir, "return ticket -MOULD.docx")
        if not os.path.exists(path):
            self.skipTest("模板文件不存在")
        placeholders = scan_template(path)
        self.assertGreater(len(placeholders), 0)
        # 应当包含 随机四位数、护照号 等
        print(f"\n  Return ticket placeholders: {placeholders}")

    def test_return_ticket_mapping(self):
        path = os.path.join(self.mould_dir, "return ticket -MOULD.docx")
        if not os.path.exists(path):
            self.skipTest("模板文件不存在")
        mapping = generate_mapping(path)
        # 动态字段应有值
        for name in ["随机四位数", "当前日期", "当前时间", "随机六位数"]:
            if name in mapping:
                self.assertNotEqual(mapping[name], "", f"{name} 应该有自动生成的值")
        print(f"\n  Return ticket mapping: {mapping}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

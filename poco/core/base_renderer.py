"""
渲染器抽象基类 — 定义多格式统一接口。

所有渲染器（DocxRenderer, OdtRenderer, 未来的 PdfRenderer 等）
必须实现此基类定义的三个核心方法:
  - load():   加载模板文件
  - fill():   用数据填充占位符
  - save():   保存到输出路径

扩展接口（可选重写）:
  - extract_placeholders(): 从模板中提取占位符列表
  - validate():             校验模板与数据的匹配情况
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseRenderer(ABC):
    """
    文档渲染器抽象基类。

    子类必须实现 load / fill / save 方法。
    可选重写 extract_placeholders / validate 方法。

    生命周期:
        renderer = ConcreteRenderer()
        renderer.load(template_path)         # 1. 加载
        renderer.fill(data)                   # 2. 填充
        renderer.save(output_path)            # 3. 保存

    或使用便捷方法:
        renderer.process(template_path, data, output_path)  # 1+2+3
    """

    # ---- 子类必须实现 -------------------------------------------------------

    @abstractmethod
    def load(self, file_path: str) -> None:
        """
        加载模板文件到内存。

        Args:
            file_path: 模板文件路径

        Raises:
            FileNotFoundError: 文件不存在
            ValueError:        格式不兼容
        """
        ...

    @abstractmethod
    def fill(self, data: Dict[str, str]) -> None:
        """
        将数据填充到已加载的模板中。

        Args:
            data: {占位符名称: 替换值} 映射表

        Raises:
            ValueError: 存在无法填充的占位符
        """
        ...

    @abstractmethod
    def save(self, output_path: str) -> None:
        """
        将填充后的文档保存到指定路径。

        Args:
            output_path: 输出文件路径（目录不存在时自动创建）
        """
        ...

    # ---- 可选重写 -----------------------------------------------------------

    def extract_placeholders(self) -> List[str]:
        """
        从已加载的模板中提取所有占位符名称。

        默认实现返回空列表；子类应重写此方法。

        Returns:
            占位符名称列表（去重，按首次出现顺序）
        """
        return []

    def validate(self, data: Dict[str, str]) -> List[str]:
        """
        校验数据是否覆盖模板中的所有占位符。

        默认实现基于 extract_placeholders() 做简单比对；
        子类可重写以添加格式校验等逻辑。

        Args:
            data: {占位符名称: 替换值} 映射表

        Returns:
            缺失的占位符名称列表（空列表 = 校验通过）
        """
        placeholders = self.extract_placeholders()
        missing: List[str] = []
        for ph in placeholders:
            if ph not in data:
                missing.append(ph)
        return missing

    # ---- 便捷方法 -----------------------------------------------------------

    def process(
        self,
        template_path: str,
        data: Dict[str, str],
        output_path: str,
    ) -> None:
        """
        一站式处理：加载 → 填充 → 保存。

        Args:
            template_path: 模板文件路径
            data:          {占位符名称: 替换值} 映射表
            output_path:   输出文件路径
        """
        self.load(template_path)
        self.fill(data)
        self.save(output_path)

    # ---- 错误格式化 ---------------------------------------------------------

    @staticmethod
    def _error_tag(tag: str, message: str) -> str:
        """
        生成统一的错误标签格式。

        Args:
            tag:     错误标签（如 "DOCX_RENDER_ERROR"）
            message: 错误描述

        Returns:
            格式化后的错误字符串，例如 "[DOCX_RENDER_ERROR] missing field: name"
        """
        return f"[{tag}] {message}"

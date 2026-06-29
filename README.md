# POCO — 文档自动生成工具

POCO（Portable Office Content Organizer） 是一个基于 Python 开发的文档自动生成工具，支持 DOCX 和 ODT 模板自动填充，并可一键导出 PDF。项目提供 Streamlit Web 界面，适用于重复性文档生成场景。POCO 是我为解决重复文档填写工作而开发的自动化办公工具，目前作为个人开源项目持续维护。

## 功能特性
✅ 支持 DOCX 模板
✅ 支持 ODT 模板
✅ 自动识别模板格式
✅ 自动扫描模板占位符
✅ 自动填充模板内容
✅ 导出 PDF（基于 LibreOffice）
✅ Streamlit Web 界面
✅ 模板管理
✅ 多格式统一文档引擎

## 环境要求

- Windows 10+
- Python 3.10+（仅用于创建虚拟环境）
- LibreOffice（用于 PDF 导出）

## 首次运行

```
install.bat
```

该脚本会：
1. 创建项目独立的 Python 虚拟环境（`.venv`）
2. 安装所有依赖

## 日常启动

```
start_poco.bat
```

启动后访问 http://localhost:8501

## 项目结构

```
POCO/
├── poco/           # 核心模块
│   ├── core/       # 文档引擎 & 格式检测
│   ├── renderers/  # DOCX / ODT 渲染器
│   ├── rules/      # 业务规则 & 日期规则
│   ├── templates/  # 模板注册 & 存储
│   ├── ui/         # Streamlit Web 界面
│   ├── auth/       # 用户认证
│   ├── logs/       # 生成日志
│   └── utils/      # 工具函数
├── tests/          # 单元测试
├── install.bat     # 首次环境安装
├── start_poco.bat  # 日常启动脚本
├── requirements.txt
└── README.md
```

## 技术栈
```
Python 3.12
Streamlit
python-docx
LibreOffice
XML / ZIP（ODT 解析）
```

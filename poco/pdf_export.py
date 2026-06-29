"""
POCO PDF 导出模块 — 基于 LibreOffice 的 Word → PDF 转换。

功能：
    - 自动检测 LibreOffice 是否已安装（Windows / Linux / Docker）
    - 将 .docx 文件转换为 .pdf（无头模式，无需 GUI）
    - 完整的日志输出与异常处理，不因 PDF 导出失败导致 POCO 崩溃

兼容：
    - Windows（soffice.exe）
    - Linux / Docker（soffice）

依赖：
    - 仅使用 Python 标准库（os, shutil, subprocess, time, logging）
    - 不依赖任何第三方 pip 包
"""

import logging
import os
import shutil
import subprocess
import time

# ---------------------------------------------------------------------------
# 模块级 logger，与 POCO 现有日志体系兼容
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ===========================================================================
#  LibreOffice 检测
# ===========================================================================

def check_libreoffice() -> bool:
    """
    检测当前系统是否安装了 LibreOffice。

    检测策略（按优先级依次尝试）：
        1. shutil.which() — 在系统 PATH 环境变量中查找可执行文件
        2. Windows 常见安装目录扫描（Program Files / Program Files (x86)）
        3. 直接 subprocess 调用尝试

    Returns:
        True  — LibreOffice 已安装且可调用
        False — 未安装或不可调用
    """
    # 根据操作系统确定可执行文件名
    exe_name = "soffice.exe" if os.name == "nt" else "soffice"

    # ---- 策略 1: PATH 环境变量查找 ----
    found = shutil.which(exe_name)
    if found:
        logger.info("在 PATH 中检测到 LibreOffice: %s", found)
        print(f"[OK] 检测到 LibreOffice: {found}")
        return True

    # ---- 策略 2: Windows 常见安装目录 ----
    if os.name == "nt":
        # 收集所有可能的安装路径
        prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        prog_files_x86 = os.environ.get(
            "ProgramFiles(x86)", "C:\\Program Files (x86)"
        )

        # LibreOffice 版本号可能不同（LibreOffice, LibreOffice24, LibreOffice25 等）
        possible_dirs = [
            os.path.join(prog_files, "LibreOffice", "program", "soffice.exe"),
            os.path.join(prog_files_x86, "LibreOffice", "program", "soffice.exe"),
        ]

        # 同时扫描 LibreOffice* 命名的目录（例如 LibreOffice 24, LibreOffice 25）
        for base in [prog_files, prog_files_x86]:
            if not os.path.isdir(base):
                continue
            try:
                for entry in os.listdir(base):
                    if entry.lower().startswith("libreoffice"):
                        candidate = os.path.join(
                            base, entry, "program", "soffice.exe"
                        )
                        if candidate not in possible_dirs:
                            possible_dirs.append(candidate)
            except OSError:
                pass  # 目录不可读，跳过

        for path in possible_dirs:
            if os.path.isfile(path):
                logger.info("在安装目录中检测到 LibreOffice: %s", path)
                print(f"[OK] 检测到 LibreOffice: {path}")
                return True

    # ---- 策略 3: 直接 subprocess 调用尝试 ----
    try:
        result = subprocess.run(
            [exe_name, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            # Windows 下禁止弹窗
            creationflags=(
                subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            ),
        )
        if result.returncode == 0:
            version_str = result.stdout.strip()
            logger.info("通过 subprocess 检测到 LibreOffice: %s", version_str)
            print(f"[OK] 检测到 LibreOffice: {version_str}")
            return True
    except FileNotFoundError:
        pass  # 可执行文件不在 PATH 中
    except subprocess.TimeoutExpired:
        logger.debug("LibreOffice --version 调用超时")
    except Exception as e:
        logger.debug("subprocess 检测 LibreOffice 时出现异常: %s", e)

    # ---- 所有策略均未找到 ----
    logger.warning("未检测到 LibreOffice。")
    print("[!] 未检测到 LibreOffice。")
    return False


# ===========================================================================
#  DOCX → PDF 转换
# ===========================================================================

def docx_to_pdf(docx_path: str, pdf_path: str) -> bool:
    """
    使用 LibreOffice 无头模式将 .docx 文件转换为 .pdf。

    转换过程：
        1. 前置校验（DOCX 存在、LibreOffice 可用）
        2. 清理可能存在的同名旧 PDF 文件
        3. 调用 soffice --headless --convert-to pdf
        4. 等待转换完成（最长 120 秒超时）
        5. 将 LibreOffice 默认输出路径的 PDF 移动到目标路径
        6. 输出完整日志（成功/失败/耗时/错误原因）

    Args:
        docx_path: 源 .docx 文件的绝对路径
        pdf_path:  目标 .pdf 文件的绝对路径

    Returns:
        True  — 转换成功，pdf_path 即为最终 PDF 文件路径
        False — 转换失败（文件不存在 / LibreOffice 缺失 / 超时 / 异常）

    Note:
        LibreOffice 默认将 PDF 输出到源文件所在目录，
        文件名与源文件同名（扩展名变为 .pdf）。
        本函数会将该默认输出移动到指定的 pdf_path，
        确保调用方拿到正确的文件路径。
    """
    # =======================================================================
    #  前置校验 1: DOCX 源文件是否存在
    # =======================================================================
    if not os.path.isfile(docx_path):
        msg = f"DOCX 文件不存在: {docx_path}"
        logger.error(msg)
        print(f"[ERR] {msg}")
        return False

    # =======================================================================
    #  前置校验 2: LibreOffice 是否可用
    # =======================================================================
    if not check_libreoffice():
        msg = "当前服务器未安装 LibreOffice。"
        logger.error(msg)
        print(f"[ERR] {msg}")
        return False

    # =======================================================================
    #  准备工作：确定路径、清理旧文件
    # =======================================================================
    exe_name = "soffice.exe" if os.name == "nt" else "soffice"

    # 源文件所在目录（LibreOffice 默认输出到此目录）
    docx_dir = os.path.dirname(os.path.abspath(docx_path))
    docx_basename = os.path.basename(docx_path)
    # LibreOffice 默认在同目录生成 <原文件名>.pdf
    default_pdf_name = os.path.splitext(docx_basename)[0] + ".pdf"
    default_pdf_path = os.path.join(docx_dir, default_pdf_name)

    # 清理目标路径的旧文件（避免干扰判断）
    for path in [pdf_path, default_pdf_path]:
        if os.path.isfile(path):
            try:
                os.remove(path)
                logger.debug("已删除旧文件: %s", path)
            except OSError as e:
                logger.warning("无法删除旧文件 %s: %s", path, e)

    # =======================================================================
    #  日志：开始转换
    # =======================================================================
    logger.info("开始转换 PDF...")
    logger.info("  DOCX: %s", docx_path)
    logger.info("  PDF:  %s", pdf_path)
    logger.info("  输出目录: %s", docx_dir)

    print(f"\n[PDF] 开始转换 PDF...")
    print(f"   DOCX: {os.path.basename(docx_path)}")
    print(f"   PDF:  {os.path.basename(pdf_path)}")
    print(f"   调用 LibreOffice...")

    # =======================================================================
    #  调用 LibreOffice 无头模式进行转换
    # =======================================================================
    start_time = time.time()

    try:
        # 构建命令行参数
        #   --headless      : 无 GUI 模式，不弹窗口
        #   --convert-to pdf: 输出格式为 PDF
        #   --outdir        : 指定输出目录
        cmd = [
            exe_name,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", docx_dir,
            docx_path,
        ]

        logger.debug("执行命令: %s", " ".join(cmd))

        # Windows 下设置 CREATE_NO_WINDOW 避免弹出控制台窗口
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 120 秒超时保护
            creationflags=creationflags,
        )

        elapsed = time.time() - start_time

        # ===================================================================
        #  检查返回码
        # ===================================================================
        if result.returncode != 0:
            logger.error(
                "LibreOffice 返回非零退出码: %d\n"
                "  stdout: %s\n"
                "  stderr: %s",
                result.returncode,
                result.stdout.strip() or "(空)",
                result.stderr.strip() or "(空)",
            )
            print(f"[ERR] 转换失败（退出码: {result.returncode}）")
            if result.stderr:
                print(f"   错误输出: {result.stderr.strip()}")
            return False

        # ===================================================================
        #  验证输出文件 — 处理 LibreOffice 输出路径
        # ===================================================================
        # LibreOffice 将 PDF 输出到 --outdir 指定的目录下，
        # 文件名为 <原文件名>.pdf
        if os.path.isfile(default_pdf_path):
            # 将默认输出路径的 PDF 移动到调用方指定的目标路径
            if os.path.abspath(default_pdf_path) != os.path.abspath(pdf_path):
                # 如果目标路径所在目录不存在，创建之
                pdf_target_dir = os.path.dirname(pdf_path)
                if pdf_target_dir and not os.path.isdir(pdf_target_dir):
                    os.makedirs(pdf_target_dir, exist_ok=True)
                shutil.move(default_pdf_path, pdf_path)
                logger.info(
                    "已将 PDF 从默认位置移动到目标路径:\n"
                    "  源: %s\n"
                    "  目标: %s",
                    default_pdf_path,
                    pdf_path,
                )

            logger.info("[OK] 转换成功。耗时: %.1f 秒", elapsed)
            print(f"[OK] 转换成功。耗时: {elapsed:.1f} 秒")
            return True

        # 极少数情况下 LibreOffice 可能直接将 PDF 输出到目标路径
        if os.path.isfile(pdf_path):
            logger.info("[OK] 转换成功（PDF 已位于目标路径）。耗时: %.1f 秒", elapsed)
            print(f"[OK] 转换成功。耗时: {elapsed:.1f} 秒")
            return True

        # ===================================================================
        #  输出文件未找到 — 诊断信息
        # ===================================================================
        logger.error(
            "转换命令执行成功但未找到输出 PDF 文件。\n"
            "  默认预期路径: %s\n"
            "  目标路径:     %s\n"
            "  LibreOffice stdout: %s\n"
            "  LibreOffice stderr: %s",
            default_pdf_path,
            pdf_path,
            result.stdout.strip() or "(空)",
            result.stderr.strip() or "(空)",
        )
        print(f"[ERR] 转换后未找到 PDF 文件。")
        print(f"   预期位置: {default_pdf_path}")
        return False

    # =======================================================================
    #  异常处理 — 捕获所有可能的异常，绝不向上抛出
    # =======================================================================
    except FileNotFoundError:
        elapsed = time.time() - start_time
        logger.error(
            "找不到 LibreOffice 可执行文件: %s（耗时 %.1f 秒）",
            exe_name,
            elapsed,
        )
        print(f"[ERR] 当前服务器未安装 LibreOffice。")
        return False

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        logger.error(
            "LibreOffice 转换超时（超过 120 秒）。\n"
            "  源文件: %s\n"
            "  已等待: %.1f 秒",
            docx_path,
            elapsed,
        )
        print(f"[ERR] 转换超时（超过 120 秒）。")
        return False

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            "转换过程中发生未预期异常。\n"
            "  异常类型: %s\n"
            "  异常信息: %s\n"
            "  耗时: %.1f 秒",
            type(e).__name__,
            e,
            elapsed,
            exc_info=True,
        )
        print(f"[ERR] 转换失败。")
        print(f"   异常原因: {e}")
        return False

#!/usr/bin/env python3
"""
脱敏复制脚本：从 logseq_sycamore 复制内容到 obs_syca，过滤隐私标记的行
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

# ========== 配置区域 ==========
SOURCE_DIR = Path("/Users/syca/01work/logseq_sycamore")
TARGET_DIR = Path("/Users/syca/01work/obs_syca")

# 隐私标记（行包含这些关键词会被过滤）
PRIVATE_KEYWORDS = [
    "#private",
    "#证件",
    "#密码",
    "#token",
    "身份证",
    "银行卡号",
    "密码",
    "API_KEY",
    "SECRET",
    "PRIVATE",
    "证件照",
]

# 整个文件如果包含这些标签，跳过该文件（保护整个文件）
SKIP_FILE_TAGS = ["#private/全文", "#绝密", "#top-secret"]

# 需要处理的文件扩展名
EXTENSIONS = {".md", ".org", ".txt"}

# 是否保留空目录（False = 删除空目录）
KEEP_EMPTY_DIRS = False

# 是否输出详细日志
VERBOSE = True
# ========== 配置结束 ==========


def should_skip_file(file_path: Path) -> bool:
    """检查整个文件是否应该跳过（基于文件头部的标签）"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # 只读前 50 行，通常标签都在文件开头
            for i, line in enumerate(f):
                if i > 50:
                    break
                for tag in SKIP_FILE_TAGS:
                    if tag in line:
                        return True
    except Exception as e:
        print(f"⚠️ 读取文件失败 {file_path}: {e}")
    return False


def filter_content(content: str) -> tuple[str, bool]:
    """
    过滤内容中的隐私行
    返回: (过滤后的内容, 是否有内容保留)
    """
    lines = content.splitlines(keepends=True)
    filtered_lines = []
    has_content = False

    for line in lines:
        # 检查是否包含隐私关键词
        is_private = False
        for keyword in PRIVATE_KEYWORDS:
            if keyword.lower() in line.lower():
                is_private = True
                if VERBOSE:
                    print(f"   🚫 过滤隐私行: {line.strip()[:50]}...")
                break

        if not is_private:
            filtered_lines.append(line)
            if line.strip():  # 非空行
                has_content = True

    return "".join(filtered_lines), has_content


def add_privacy_notice(content: str, source_file: str) -> str:
    """在文件开头添加脱敏说明"""
    notice = f"""---
# 此文件由自动脱敏脚本生成
# 原始来源: {source_file}
# 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# 说明: 已过滤隐私内容（证件、密码等），如需原始内容请查看 Logseq
---

"""
    return notice + content


def copy_and_filter(src: Path, dst: Path) -> bool:
    """复制并过滤单个文件"""
    try:
        # 读取原始内容
        with open(src, "r", encoding="utf-8") as f:
            original_content = f.read()

        # 过滤内容
        filtered_content, has_content = filter_content(original_content)

        if not has_content:
            if VERBOSE:
                print(f"⏭️  跳过（无有效内容）: {src}")
            return False

        # 添加脱敏说明
        final_content = add_privacy_notice(filtered_content, str(src))

        # 写入目标文件
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(final_content)

        if VERBOSE:
            original_size = len(original_content)
            filtered_size = len(final_content)
            if filtered_size < original_size:
                reduction = (1 - filtered_size / original_size) * 100
                print(f"✅ 已脱敏: {src} -> {dst} (减少 {reduction:.1f}%)")
            else:
                print(f"✅ 已复制: {src} -> {dst}")

        return True

    except Exception as e:
        print(f"❌ 处理失败 {src}: {e}")
        return False


def clean_empty_dirs(directory: Path):
    """删除空目录（可选）"""
    if not KEEP_EMPTY_DIRS:
        for dirpath in sorted(directory.rglob("*"), reverse=True):
            if dirpath.is_dir() and not any(dirpath.iterdir()):
                dirpath.rmdir()
                if VERBOSE:
                    print(f"🗑️  删除空目录: {dirpath}")


def main():
    print("=" * 60)
    print("脱敏复制脚本")
    print(f"源目录: {SOURCE_DIR}")
    print(f"目标目录: {TARGET_DIR}")
    print("=" * 60)

    if not SOURCE_DIR.exists():
        print(f"❌ 错误: 源目录不存在 {SOURCE_DIR}")
        return

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    stats = {"processed": 0, "skipped": 0, "failed": 0, "total": 0}

    # 遍历源目录
    for src_path in SOURCE_DIR.rglob("*"):
        if src_path.suffix not in EXTENSIONS:
            continue

        stats["total"] += 1

        # 检查是否跳过整个文件
        if should_skip_file(src_path):
            print(f"⏭️  跳过整个文件（含敏感标签）: {src_path}")
            stats["skipped"] += 1
            continue

        # 计算目标路径
        rel_path = src_path.relative_to(SOURCE_DIR)
        dst_path = TARGET_DIR / rel_path

        if copy_and_filter(src_path, dst_path):
            stats["processed"] += 1
        else:
            stats["failed"] += 1

    # 清理空目录
    clean_empty_dirs(TARGET_DIR)

    # 输出统计
    print("\n" + "=" * 60)
    print("📊 统计结果:")
    print(f"  总文件数: {stats['total']}")
    print(f"  ✅ 已处理: {stats['processed']}")
    print(f"  ⏭️  已跳过: {stats['skipped']}")
    print(f"  ❌ 失败: {stats['failed']}")
    print(f"  目标位置: {TARGET_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
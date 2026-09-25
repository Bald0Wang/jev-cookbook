"""生成简介、快速开始、AI 入门及四个概念章节 Notebook；输出位置基于脚本路径。"""
import importlib

CHAPTERS = [
    ("introduction", "认识 Jev（合并简介/快速开始/场景地图/AI 入门）"),
    ("system_one", "System One"),
    ("state", "State"),
    ("build_with_typesafe", "如何用 TypeSafe 构建"),
]


def main():
    for slug, _ in CHAPTERS:
        path = importlib.import_module(f"build_{slug}_notebook").build()
        print(path.name)


if __name__ == "__main__":
    main()

"""生成简介、快速开始、AI 入门及四个概念章节 Notebook；输出位置基于脚本路径。"""
import importlib

CHAPTERS = [
    ("introduction", "简介"), ("quickstart", "快速开始"),
    ("ai_primer", "AI 入门"), ("system_one", "System One"),
    ("state", "State"), ("build_with_typesafe", "如何用 TypeSafe 构建"),
    ("use_case_map", "应用场景地图"),
]


def main():
    for slug, _ in CHAPTERS:
        path = importlib.import_module(f"build_{slug}_notebook").build()
        print(path.name)


if __name__ == "__main__":
    main()

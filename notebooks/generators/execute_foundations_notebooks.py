"""在干净内核顺序执行章节；离线输出单独存放，真实验收拒绝回退。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

from build_foundations_notebooks import CHAPTERS
from notebook_support import PENDING_STATUS, FILENAMES

ROOT = Path(__file__).resolve().parents[1]


def structure_report(nb):
    nbformat.validate(nb)
    code = [cell for cell in nb.cells if cell.cell_type == "code"]
    md_count = sum(cell.cell_type == "markdown" for cell in nb.cells)
    maximum = max(len(cell.source.splitlines()) for cell in code)
    if maximum > 30 or not 1.4 <= md_count / len(code) <= 1.65:
        raise ValueError("单元格长度或说明密度不符合本项目标准")
    for cell in code:
        if any(output.output_type == "error" for output in cell.get("outputs", [])):
            raise ValueError("发现错误输出")
    return {"markdown_cells": md_count, "code_cells": len(code), "max_code_lines": maximum}


def get_audit(nb):
    cells = [c for c in nb.cells if "execution-audit" in c.metadata.get("tags", [])]
    if len(cells) != 1:
        raise ValueError("缺少唯一的执行来源记录")
    output = "".join(x.get("text", "") for x in cells[0].outputs if x.output_type == "stream")
    audit = json.loads(output)
    if audit["kind"] != "jev_execution_audit":
        raise ValueError("执行记录类型不匹配")
    return audit


def assert_no_key(text, key):
    if key and key in text:
        raise ValueError("结果包含环境变量中的密钥，停止保存")


def execute_one(slug, mode, key):
    source = ROOT / f"{FILENAMES.get(slug, slug + '_experiments')}.ipynb"
    nb = nbformat.read(source, as_version=4)
    dimensions = structure_report(nb)
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
    env = os.environ.copy()
    env["JEV_RUN_MODE"] = mode
    if mode == "offline":
        env.pop("TYPESAFE_API_KEY", None)
    # 确保内核与执行器使用同一 Python；工作目录为空，验证无隐藏本地文件依赖。
    with tempfile.TemporaryDirectory(prefix="jev-kernel-") as workdir:
        env["IPYTHONDIR"] = str(Path(workdir) / "ipython")
        env["JUPYTER_RUNTIME_DIR"] = str(Path(workdir) / "runtime")
        manager = KernelManager(kernel_name="python3")
        manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
        runner = NotebookClient(nb, km=manager, timeout=180, startup_timeout=30,
                                allow_errors=False, resources={"metadata": {"path": workdir}})
        try:
            runner.execute(env=env)
        finally:
            if manager.has_kernel:
                manager.shutdown_kernel(now=True)
            manager.cleanup_resources()
    dimensions = structure_report(nb)
    audit = get_audit(nb)
    if mode == "live":
        if audit["offline_calls"] or audit["ping"]["source"] != "live" or not audit["real_calls"]:
            raise ValueError("真实验收出现离线结果或没有真实请求")
        output_text = "\n".join(str(c.get("outputs", [])) for c in nb.cells if c.cell_type == "code")
        if "离线示例" in output_text:
            raise ValueError("真实执行输出含离线回退标记")
        destination = source
        # 封面是生成器写出的未执行状态，在真实执行后同步更新；内容仍来自生成器。
        nb.cells[0].source = nb.cells[0].source.replace(
            PENDING_STATUS,
            "**本文件已执行真实 API。** 具体模型、日期、调用次数及分支缺口见末尾记录；仍需人工核对语义结论。")
    else:
        if audit["real_calls"] or audit["ping"]["source"] != "offline":
            raise ValueError("离线执行不应发起真实调用")
        destination = ROOT / "validation" / "offline_previews" / source.name
        nb.cells[0].source = "# 离线预览：人工答案，不是 Jev 实测\n\n" + nb.cells[0].source
    nb.metadata["jev_cookbook"]["live_validation"] = audit["validation_status"]
    serialized = nbformat.writes(nb)
    assert_no_key(serialized, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialized, encoding="utf-8")
    return {"chapter": slug, "file": str(destination.relative_to(ROOT)), **dimensions, **audit}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["offline", "live"], default="live")
    parser.add_argument("--chapter", choices=[slug for slug, _ in CHAPTERS])
    args = parser.parse_args(argv)
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if args.mode == "live" and not key:
        parser.error("未配置 TYPESAFE_API_KEY；没有执行或改写任何 Notebook。可先用 --mode offline。")
    selected = [slug for slug, _ in CHAPTERS if not args.chapter or slug == args.chapter]
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
              "status": "running", "chapters": []}
    failed = False
    for slug in selected:
        print(f"执行 {slug}（{args.mode}）", flush=True)
        try:
            report["chapters"].append(execute_one(slug, args.mode, key))
        except Exception as error:
            # 不把可能含认证上下文的异常字符串写入报告。
            report["failure"] = {"chapter": slug, "type": type(error).__name__}
            report["status"] = "failed"
            print(f"执行失败：{type(error).__name__}；请在本地检查该章，未保存本次失败输出。", file=sys.stderr)
            failed = True
            break
    if not failed:
        report["status"] = "offline_verified_live_pending" if args.mode == "offline" else "live_executed_manual_review_pending"
    report_path = ROOT / "validation" / f"foundations-{args.mode}{'-' + args.chapter if args.chapter else ''}.json"
    report_path.parent.mkdir(exist_ok=True)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    assert_no_key(serialized, key)
    report_path.write_text(serialized + "\n", encoding="utf-8")
    print(f"记录：{report_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

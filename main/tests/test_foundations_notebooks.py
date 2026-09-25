"""用真实 SDK 的本地 MockTransport 检查新教材所有请求与响应契约；不访问网络。"""
import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "generators"))
from notebook_support import FILENAMES
from unittest.mock import patch

import httpx2
import nbformat
from typesafe_sdk import RetryPolicy, TypeSafeClient, TypeSafeAuthenticationError, TypeSafeError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generators"))
from build_foundations_notebooks import CHAPTERS
from execute_foundations_notebooks import assert_no_key, structure_report


def execute_with_transport(slug):
    nb = nbformat.read(ROOT / f"{FILENAMES.get(slug, slug + '_experiments')}.ipynb", as_version=4)
    scope = {}
    serialized_requests = []

    def contract_call(state, questions, offline_answers, label):
        answers = {key: dict(answer.__dict__) for key, answer in offline_answers.items()}
        payload = {"model": "sdk-contract-test", "answers": answers,
                   "usage": {"input_tokens": 1, "output_tokens": 1}}

        def handler(request):
            body = json.loads(request.content)
            if body["state"] != state or set(body["questions"]) != set(questions):
                raise AssertionError("SDK 序列化改变了 state 或问题 ID")
            serialized_requests.append(body)
            return httpx2.Response(200, json=payload)

        with TypeSafeClient(api_key="contract-test-placeholder", model="jev-1.13.0",
                            transport=httpx2.MockTransport(handler),
                            retry=RetryPolicy(max_retries=0)) as local_client:
            response = local_client.system_one(state, questions)
        scope["validate_response"](response, questions)
        # 只保留本地测试来源，避免把 MockTransport 的 SDK 路径称为真实 API。
        scope["CALL_LOG"].append({"case": label, "source": "offline", "model": "sdk-contract-test",
                                  "seconds": None, "input_tokens": 0, "output_tokens": 0})
        return response

    with patch.dict(os.environ, {"JEV_RUN_MODE": "offline", "TYPESAFE_API_KEY": ""}), contextlib.redirect_stdout(io.StringIO()):
        for cell in nb.cells:
            if cell.cell_type != "code" or "%pip" in cell.source:
                continue
            exec(compile(cell.source, f"{slug}:{cell.id}", "exec"), scope)
            if "ts" in scope:
                scope["ts"].call = contract_call
    return scope, serialized_requests


class NotebookContracts(unittest.TestCase):
    def test_all_chapters_pass_sdk_serialization_and_response_parsing(self):
        total = 0
        for slug, _ in CHAPTERS:
            with self.subTest(chapter=slug):
                scope, requests = execute_with_transport(slug)
                total += len(requests)
                self.assertGreater(len(requests), 0)
                self.assertEqual(scope["AUDIT"]["real_calls"], 0)
                if slug == "build_with_typesafe":
                    self.assertEqual(scope["COVERAGE"]["missing"], [])
                    self.assertNotIn("closed", [x["case"] for x in scope["CALL_LOG"]])
                for request in requests:
                    self.assertNotIn("expected_label", json.dumps(request["state"]))
        self.assertGreaterEqual(total, 20)  # 合并后章节数变化，仅保底断言

    def test_strict_live_does_not_hide_authentication_failure(self):
        scope, _ = execute_with_transport("introduction")
        with TypeSafeClient(api_key="contract-test-placeholder", transport=httpx2.MockTransport(
            lambda request: httpx2.Response(401, json={"detail": "Invalid credentials"})),
            retry=RetryPolicy(max_retries=0)) as local_client:
            scope["client"] = local_client
            scope["RUN_MODE"] = "live"
            # 从类建立新实例，避免上个测试安装在实例上的 transport 探针。
            with self.assertRaises(TypeSafeAuthenticationError):
                scope["TS"]().call(scope["EXP_STATE"], scope["EXP_QUESTIONS"], scope["EXP_OFFLINE"], "401")
            scope["RUN_MODE"] = "auto"
            with contextlib.redirect_stdout(io.StringIO()):
                response = scope["TS"]().call(scope["EXP_STATE"], scope["EXP_QUESTIONS"], scope["EXP_OFFLINE"], "401")
            self.assertIn("人工", response.model)
            self.assertEqual(scope["CALL_LOG"][-1]["source"], "offline")

    def test_auto_does_not_hide_server_failure(self):
        scope, _ = execute_with_transport("introduction")
        with TypeSafeClient(api_key="contract-test-placeholder", transport=httpx2.MockTransport(
            lambda request: httpx2.Response(500, json={"detail": "Server error"})),
            retry=RetryPolicy(max_retries=0)) as local_client:
            scope["client"], scope["RUN_MODE"] = local_client, "auto"
            with self.assertRaises(TypeSafeError):
                scope["TS"]().call(scope["EXP_STATE"], scope["EXP_QUESTIONS"], scope["EXP_OFFLINE"], "500")

    def test_structure_and_key_export_guard(self):
        for slug, _ in CHAPTERS:
            nb = nbformat.read(ROOT / f"{FILENAMES.get(slug, slug + '_experiments')}.ipynb", as_version=4)
            report = structure_report(nb)
            self.assertLessEqual(report["max_code_lines"], 30)
        with self.assertRaises(ValueError):
            assert_no_key("prefix-local-secret-suffix", "local-secret")
        assert_no_key("不含密钥的输出", "local-secret")


if __name__ == "__main__":
    unittest.main()

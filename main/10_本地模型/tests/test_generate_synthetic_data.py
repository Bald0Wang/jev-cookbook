import json
import itertools
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_synthetic_data as generator


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "laya" / "data_generation" / "spec.example.json"


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.spec = generator.load_spec(SPEC)

    def test_label_indices_follow_candidate_order(self):
        item = {
            "state": {"subject": "产品打不开", "body": "点击后提示故障。"},
            "labels": {"department": "other", "urgent": True, "severity": 2},
            "evidence": {"department": "尚无证据表明是产品功能故障。"},
        }
        record = generator.make_record(self.spec, item, "deepseek-flash", "run", 1, "mock")
        self.assertEqual(record["qs"][0]["y"], 2)
        self.assertEqual(record["qs"][1]["y"], 1)
        self.assertEqual(record["qs"][2]["y"], 2)
        serialized = json.loads(generator.json_text(record))
        self.assertEqual(list(serialized["qs"][0]["crit"]), ["billing", "technical", "other"])
        self.assertEqual(serialized["split"], "train_candidate")
        self.assertEqual(serialized["metadata"]["review_status"], "needs_human_review")

    def test_invalid_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            generator.make_record(
                self.spec,
                {"state": "工单", "labels": {"department": "missing", "urgent": False, "severity": 0}},
                "deepseek-flash", "run", 1, "mock",
            )

    def test_mock_api_writes_laya_jsonl(self):
        items = [
            {
                "state": {"subject": "重复扣款", "body": "账单扣款两次，今天请退款。"},
                "labels": {"department": "billing", "urgent": True, "severity": 2},
                "evidence": {"urgent": "今天请退款"},
            },
            {
                "state": {"subject": "页面报错", "body": "提交时出现错误，暂时无法使用。"},
                "labels": {"department": "technical", "urgent": False, "severity": 1},
                "evidence": {"department": "提交时出现错误"},
            },
            {
                "state": {"subject": "发票开具", "body": "已付款，想申请公司抬头发票，不影响使用。"},
                "labels": {"department": "billing", "urgent": False, "severity": 0},
                "evidence": {"department": "申请公司抬头发票"},
            },
            {
                "state": {"subject": "想了解积分规则", "body": "请问积分兑换优惠券后多久过期？"},
                "labels": {"department": "other", "urgent": False, "severity": 0},
                "evidence": {"department": "咨询积分兑换"},
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "pilot.jsonl"
            barrier = threading.Barrier(2)
            call_number = itertools.count()

            def fake_call(*args, **kwargs):
                batch = next(call_number)
                barrier.wait(timeout=3)
                return {"items": items[batch * 2:batch * 2 + 2]}, "mock-%d" % batch, {
                    "prompt_tokens": 10, "completion_tokens": 20,
                }

            argv = [
                "generate_synthetic_data.py", "--spec", str(SPEC), "--out", str(output_path),
                "--count", "4", "--batch-size", "2", "--workers", "2",
            ]
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "unit-test-only"}), \
                    patch.object(generator, "call_api", fake_call), patch.object(sys, "argv", argv):
                self.assertEqual(generator.main(), 0)

            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["qs"][0]["y"], 0)
            self.assertEqual(rows[1]["qs"][0]["y"], 1)
            self.assertTrue(all(r["metadata"]["review_status"] == "needs_human_review" for r in rows))


if __name__ == "__main__":
    unittest.main()

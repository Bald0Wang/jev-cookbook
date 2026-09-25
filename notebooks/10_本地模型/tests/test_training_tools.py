import json
import sys
import tempfile
import unittest
from pathlib import Path

LayaRoot = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LayaRoot.parent))
sys.path.insert(0, str(LayaRoot))
import finetune_reviewed_jsonl as trainer
import visualize_training as visualizer


def make_record(record_id, split, group_id=None, status="approved", label_source="human_adjudicated"):
    return {
        "id": record_id,
        "split": split,
        "source_group_id": group_id or record_id,
        "state": {"text": "中文测试样本"},
        "qs": [{"id": "q", "t": "noul", "ins": "测试？", "crit": {}, "y": 0}],
        "metadata": {"review_status": status, "label_source": label_source, "reviewer": "test-reviewer"},
    }


class TrainingToolsTests(unittest.TestCase):
    def write_rows(self, rows, temp_dir):
        path = Path(temp_dir) / "data.jsonl"
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
        return path

    def test_training_input_requires_review_and_separate_group_splits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_rows([
                make_record("a", "train"),
                make_record("b", "dev"),
            ], temp_dir)
            train, dev = trainer.load_reviewed_jsonl(path)
            self.assertEqual((len(train), len(dev)), (1, 1))

    def test_assistant_pilot_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_rows([
                make_record("a", "train", status="assistant_reviewed_pilot", label_source="deepseek_pseudo_label"),
                make_record("b", "dev", status="assistant_reviewed_pilot", label_source="deepseek_pseudo_label"),
            ], temp_dir)
            with self.assertRaises(ValueError):
                trainer.load_reviewed_jsonl(path)
            train, dev = trainer.load_reviewed_jsonl(path, allow_assistant_pilot=True)
            self.assertEqual((len(train), len(dev)), (1, 1))

    def test_group_split_leakage_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_rows([
                make_record("a", "train", group_id="same-source"),
                make_record("b", "dev", group_id="same-source"),
            ], temp_dir)
            with self.assertRaisesRegex(ValueError, "泄漏"):
                trainer.load_reviewed_jsonl(path)

    def test_html_report_contains_self_contained_svg_charts(self):
        report = {
            "gpu": "test GPU",
            "train_groups": 8,
            "dev_groups": 2,
            "review_status_counts": {"assistant_reviewed_pilot": 10},
            "dev_before": {
                "soft_cross_entropy": 0.9,
                "argmax_accuracy": 0.5,
                "by_qtype_accuracy": {"choice": 0.5, "noul": 0.5},
            },
            "dev_after": {
                "soft_cross_entropy": 0.7,
                "argmax_accuracy": 0.75,
                "by_qtype_accuracy": {"choice": 1.0, "noul": 0.5},
            },
            "history": [{
                "epoch": 1,
                "train_loss": 0.8,
                "dev": {"soft_cross_entropy": 0.7, "argmax_accuracy": 0.75},
            }],
            "peak_vram_gib": 1.5,
            "training_seconds": 5,
            "data_sha256": "data-hash",
            "base_model_sha256": "base-hash",
            "tuned_model_sha256": "tuned-hash",
        }
        page = visualizer.build_report(report)
        self.assertIn("<svg", page)
        self.assertIn("width:100%", page)
        self.assertIn("assistant_reviewed_pilot", page)
        self.assertIn("Dev 交叉熵", page)


if __name__ == "__main__":
    unittest.main()

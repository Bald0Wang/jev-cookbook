"""Frame/tick and terminal contracts without running a model or game binary."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from build_shooting_demo import AtlasWriter, HEIGHT, WIDTH, choose_default, render_episode


class Frame:
    shape, dtype = (HEIGHT, WIDTH, 3), "uint8"

    def __init__(self, tick):
        self.tick = tick

    def tobytes(self):
        return bytes([self.tick, 13, 71]) * (WIDTH * HEIGHT)


class MemoryAtlas:
    def __init__(self):
        self.count = 0

    def add(self, rgb):
        assert len(rgb) == WIDTH * HEIGHT * 3
        n = self.count
        self.count += 1
        return {"src": "media/fixture.webp", "x": n * WIDTH, "y": 0, "width": WIDTH, "height": HEIGHT}

    def finish(self):
        return []


class Game:
    def __init__(self, spec):
        self.spec, self.tick, self.calls, self.ammo, self.kills = spec, 0, [], 10., 0.

    def get_state(self):
        if self.tick == 3 and not self.spec.get("terminal_image", False):
            return None
        return SimpleNamespace(screen_buffer=Frame(self.tick))

    def get_game_variable(self, variable):
        return self.ammo if variable == "ammo" else self.kills

    def make_action(self, buttons, ticks):
        assert ticks == 1 and self.tick < 3
        self.calls.append((list(buttons), ticks))
        self.tick += 1
        self.ammo -= int(buttons[2])
        self.kills = float(self.tick == 3 and self.spec.get("win", True))
        return -.1


class Env:
    instances = []

    def __init__(self, spec):
        self.spec, self._game, self.step_index = spec, Game(spec), 0
        self.raw = self._game
        self.max_steps, self.frame_skip, self.max_ticks = 5, 2, 10
        self._vzd = SimpleNamespace(GameVariable=SimpleNamespace(SELECTED_WEAPON_AMMO="ammo", KILLCOUNT="kills"))
        self._initial = {"KILLCOUNT": 0}
        self.closed = False
        Env.instances.append(self)

    def observation(self):
        return {"task": "shooting", "state": json.dumps({"physical_tick": self.raw.tick}),
                "step": self.step_index, "remaining_steps": 0 if self.raw.tick == 3 else 3 - self.raw.tick,
                "candidates": {} if self.raw.tick == 3 else {a: a for a in ("left", "right", "noop", "shoot")}}

    def info(self, actual=0):
        done = self.raw.tick == 3
        return {"terminated": done, "truncated": False, "success": bool(self.raw.kills),
                "native_timeout_tick": 17, "episode_start_tick": 14, "actual_ticks": actual,
                "episode_metrics": {"physical_ticks": self.raw.tick, "ammo": self.raw.ammo,
                    "kills": self.raw.kills, "ammo_consumed": 10 - self.raw.ammo,
                    "native_reward": -.1 * self.raw.tick, "outcome": "target_killed" if self.raw.kills else "native_timeout"}}

    def reset(self, seed):
        return self.observation(), self.info()

    def step(self, action):
        buttons = {"left": [True, False, False], "right": [False, True, False],
                   "shoot": [False, False, True], "noop": [False, False, False]}[action]
        ticks = min(2, 3 - self.raw.tick)
        reward = sum(self._game.make_action(buttons, 1) for _ in range(ticks))
        self.step_index += 1
        return self.observation(), reward, self.raw.tick == 3, False, self.info(ticks)

    def close(self):
        self.closed = True


def episode(win=True, terminal_image=False):
    spec = {"task": "shooting", "scenario": "basic", "win": win, "terminal_image": terminal_image}
    env = Env(spec)
    obs, info = env.reset(9)
    steps = []
    for action in ("left", "shoot"):
        old = obs
        obs, reward, terminal, truncated, info = env.step(action)
        steps.append({"observation": old, "action": action,
                      "scores": {"left": .1, "noop": .2, "right": .3, "shoot": .4},
                      "reward": reward, "terminated": terminal, "truncated": truncated, "info": info})
    return {"case": {"id": "fixture", "split": "test", "seed": 9, "spec": spec},
            "complete": True, "success": win, "steps": steps, "final_info": info, "final_observation": obs}


class ShootingFrames(unittest.TestCase):
    def test_every_tick_and_previous_decision_with_terminal_fallback(self):
        source = episode()
        system, audit, budget = render_episode(source, "nanojev", MemoryAtlas(), Env)
        frames = system["frames"]
        self.assertEqual([f["tick"] for f in frames], [0, 1, 2, 3])
        self.assertEqual([f["decision"] for f in frames], [0, 1, 1, 2])
        self.assertEqual([f["action"] for f in frames], [None, "left", "left", "shoot"])
        self.assertEqual([f["image_tick"] for f in frames], [0, 1, 2, 2])
        self.assertIsNone(frames[0]["probabilities"])
        self.assertEqual(frames[1]["probabilities"], source["steps"][0]["scores"])
        self.assertEqual([f["terminal"] for f in frames], [False, False, False, True])
        self.assertEqual([f["success"] for f in frames], [False, False, False, True])
        self.assertEqual(frames[-1]["sprite"], frames[-2]["sprite"])
        self.assertEqual((budget, audit["physical_ticks"], audit["fallback_image_frames"]), (3, 3, 1))
        self.assertEqual(len(Env.instances[-1].raw.calls), 3)
        self.assertTrue(Env.instances[-1].closed)

    def test_terminal_real_image_and_failure(self):
        system, audit, _ = render_episode(episode(False, True), "base", MemoryAtlas(), Env)
        self.assertEqual(system["frames"][-1]["image_tick"], 3)
        self.assertEqual(audit["actual_rgb_images"], 4)
        self.assertFalse(system["success"])
        self.assertTrue(system["frames"][-1]["terminal"])

    def test_changed_recorded_fields_fail(self):
        for field in ("observation", "reward", "info", "terminated"):
            source = episode()
            if field == "observation":
                source["steps"][0][field]["state"] = "changed"
            elif field == "info":
                source["steps"][0][field]["extra"] = "unexpected"
            else:
                source["steps"][0][field] = 9 if field == "reward" else True
            with self.subTest(field=field), self.assertRaises(ValueError):
                render_episode(source, "jev", MemoryAtlas(), Env)
            self.assertTrue(Env.instances[-1].closed)

    def test_terminal_result_cannot_be_invented(self):
        source = episode()
        source["success"] = False
        with self.assertRaises(ValueError):
            render_episode(source, "nanojev", MemoryAtlas(), Env)

    def test_selection_does_not_invent_success_intersection(self):
        def case(cid, n, j, b, offset):
            return {"id": cid, "split": "test", "initial_target_horizontal_offset": offset,
                    "systems": [{"id": k, "success": v, "total_ticks": 10}
                                for k, v in (("nanojev", n), ("jev", j), ("base", b))]}
        cases = [case("a", True, True, True, 20), case("b", True, False, False, 40), case("c", True, False, False, -60)]
        chosen, receipt = choose_default(cases)
        self.assertEqual(chosen, "c")
        self.assertEqual(receipt["eligible_case_ids"], [])
        self.assertIn("No Jev/NanoJev-success", receipt["rule"])
        self.assertEqual(choose_default(cases, "a")[0], "a")
        with self.assertRaises(ValueError):
            choose_default(cases, "absent")

    def test_atlas_cell_mapping_and_lossless_decode(self):
        try:
            from PIL import Image, features
        except ImportError:
            self.skipTest("Pillow is an optional export dependency")
        if not features.check("webp"):
            self.skipTest("This Pillow build lacks WebP")
        with tempfile.TemporaryDirectory() as td:
            writer = AtlasWriter(Path(td) / "media", "shooting_fixture")
            a = writer.add(bytes([1, 2, 3]) * (WIDTH * HEIGHT))
            b = writer.add(bytes([7, 8, 9]) * (WIDTH * HEIGHT))
            assets = writer.finish()
            self.assertEqual((a["x"], b["x"], b["y"]), (0, 320, 0))
            self.assertEqual(assets[0]["used_cells"], 2)
            with Image.open(Path(td) / assets[0]["path"]) as atlas:
                self.assertEqual(atlas.size, (2560, 1920))
                self.assertEqual(atlas.getpixel((320, 0)), (7, 8, 9))


if __name__ == "__main__":
    unittest.main()

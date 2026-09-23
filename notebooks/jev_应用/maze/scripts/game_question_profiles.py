"""Atomic game questions, separate from the global-planning stress profile."""
import copy


def add_maze_atomic_questions(record):
    """Ask four independent propositions; IDs are never needed to interpret them."""
    from game_outcomes import DIRECTIONS
    row = copy.deepcopy(record)
    state = row["metadata"]["environment_state"]
    walls = set(map(tuple, state["walls"]))
    for action, (dr, dc) in DIRECTIONS.items():
        qid = "clear_" + action
        r, c = state["position"][0] + dr, state["position"][1] + dc
        truth = 0 <= r < state["size"] and 0 <= c < state["size"] and (r, c) not in walls
        row["questions"][qid] = {
            "type": "boolean",
            "instructions": f"Would attempting one step {action} from the current agent cell stay inside the maze and avoid a wall?",
            "criteria": {"true": "The destination is inside the board and is an open cell or the goal.",
                         "false": "The destination is outside the board or is a wall."}}
        row["gold"][qid] = truth
        row["gold_probs"][qid] = {"false": float(not truth), "true": float(truth)}
        row["gold_label_kind"][qid] = "deterministic_truth"
        row["gold_probs_kind"][qid] = "deterministic_truth"
    row["metadata"]["question_profiles"] = {
        "atomic": ["clear_" + a for a in DIRECTIONS],
        "planning_stress": [k for k in row["questions"] if not k.startswith("clear_")]}
    return row

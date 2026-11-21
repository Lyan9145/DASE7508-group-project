"""Check completeness, pairing, and outcome totals in matrix and ablation runs."""

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def check_summary(path, totals, outcomes, group_key):
    seen = set()
    for row in read_csv(path):
        key = group_key(row)
        if key in seen or key not in totals:
            raise ValueError(f"{path.name}: duplicate or unexpected group {key}")
        seen.add(key)
        n = totals[key]
        successes, aborts = outcomes[key]
        if (
            int(row["episodes"]) != n
            or int(row["successes"]) != successes
            or not math.isclose(float(row["task_success_rate"]), successes / n)
            or not math.isclose(float(row["abort_rate"]), aborts / n)
        ):
            raise ValueError(f"{path.name}: outcome totals differ for {key}")
    if seen != totals.keys():
        raise ValueError(f"{path.name}: missing summary groups")


def check_run(run):
    status = json.loads((run / "run_status.json").read_text())
    config = json.loads((run / "config.json").read_text())
    if status["complete"] is not True:
        raise ValueError(f"{run}: run is incomplete")

    if config.get("mode") == "both":
        counts = [check_run(run / mode) for mode in ("velocity", "position")]
        expected = tuple(map(sum, zip(*counts)))
    else:
        expected = check_episode_tables(run, config)

    for label, count in zip(("evaluation_episodes", "calibration_episodes"), expected):
        if status[label] != count:
            raise ValueError(f"{run}: {label} is {status[label]}, expected {count}")
    print(f"{run}: verified {expected[0]:,} evaluation rows and completion totals")
    return expected


def check_episode_tables(run, config):
    ablation = "sigmas" in config
    policies = config["policy_names"]
    n = config["episodes"]
    if ablation:
        cases = [("clean", "no_defense")] + [
            (config["attack"]["case_id"], defense) for defense in config["defenses"]
        ]
        sigmas = config["sigmas"]
        seed_base = config["seed_base"]
        episode_file = "ablation_episodes.csv"
        summary_file = "ablation_summary.csv"
    else:
        cases = list(product(
            [attack["case_id"] for attack in config["attacks"]],
            [defense["defense_id"] for defense in config["defenses"]],
        ))
        sigmas = [None]
        seed_base = config["test_base"]
        episode_file = "episodes.csv"
        summary_file = "matrix_summary.csv"
        if config["write_traces"] and not (run / "traces.jsonl.gz").is_file():
            raise ValueError(f"{run}: configured traces are missing")

    expected_keys = {
        (policy, seed, case, defense, sigma)
        for index, policy in enumerate(policies)
        for seed in range(seed_base + index * 1000, seed_base + index * 1000 + n)
        for case, defense in cases
        for sigma in sigmas
    }

    def group_key(row):
        sigma = float(row["noise_sigma"]) if ablation else None
        return row["attack_case"], row["defense"], sigma

    seen = set()
    counts = Counter()
    outcomes = defaultdict(lambda: [0, 0])
    policy_counts = Counter()
    policy_outcomes = defaultdict(lambda: [0, 0])
    for row in read_csv(run / episode_file):
        group = group_key(row)
        policy = row["policy"]
        key = (policy, int(row["seed"]), *group)
        if key in seen or key not in expected_keys:
            raise ValueError(f"{episode_file}: duplicate or unexpected episode {key}")
        seen.add(key)
        success, abort = row["task_success"], row["aborted"]
        if {success, abort} - {"True", "False"} or (success == abort == "True"):
            raise ValueError(f"{episode_file}: invalid outcome for {key}")
        counts[group] += 1
        outcomes[group][0] += success == "True"
        outcomes[group][1] += abort == "True"
        policy_counts[(policy, *group)] += 1
        policy_outcomes[(policy, *group)][0] += success == "True"
        policy_outcomes[(policy, *group)][1] += abort == "True"

    missing = expected_keys - seen
    if missing:
        raise ValueError(f"{episode_file}: missing {len(missing)} planned episodes")
    check_summary(run / summary_file, counts, outcomes, group_key)
    if not ablation:
        check_summary(
            run / "summary.csv", policy_counts, policy_outcomes,
            lambda row: (row["policy"], *group_key(row)),
        )
    return len(expected_keys), len(policies) * len(sigmas) * config["calibration_episodes"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        check_run(args.run_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Result check failed: {error}\n")


if __name__ == "__main__":
    main()

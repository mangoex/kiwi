"""Fail if scope, dependencies, source paths or reference arithmetic is incomplete.

This verifies a proposed plan; it never marks runtime or production gates green.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path

from calculos_referencia import verify_reference


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def graph_waves(tasks: list[dict]) -> list[list[str]]:
    by_id = {task["id"]: task for task in tasks}
    require(len(by_id) == len(tasks), "Duplicate task ID")
    for task in tasks:
        require(len(set(task["depends_on"])) == len(task["depends_on"]), "Duplicate dependency")
        require(set(task["depends_on"]) <= set(by_id), "Unknown dependency")
        require(task["id"] not in task["depends_on"], "Self dependency")
    done: set[str] = set()
    waves: list[list[str]] = []
    while done != set(by_id):
        ready = sorted(task_id for task_id, task in by_id.items() if task_id not in done and set(task["depends_on"]) <= done)
        require(bool(ready), "Cycle or impossible dependency")
        waves.append(ready)
        done.update(ready)
    return waves


def verify(source_root: Path, here: Path) -> dict:
    manifest = json.loads((here / "manifest.json").read_text(encoding="utf-8"))
    observed_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source_root, text=True).strip()
    require(observed_sha == manifest["baseline"], "Current source HEAD differs from plan baseline; reconcile first")
    plan = (here / "PLAN.md").read_text(encoding="utf-8")
    expected = {f"H{i:02d}" for i in range(1, 19)} | {f"B{i:02d}" for i in range(1, 6)}
    coverage = manifest["coverage"]
    require(len(coverage) == 23 and {row["id"] for row in coverage} == expected, "All 18 findings and 5 gaps must be covered exactly once")
    require(manifest["status"] == "proposed_not_implemented", "Plan must not claim implementation")
    require(not manifest["canonical_ids_changed"] and not manifest["production_authorization"], "Wrong authority or authorization claim")
    task_ids = {task["id"] for task in manifest["tasks"]}
    decisions = set(manifest["decision_ids"])
    require(decisions == {f"D{i:02d}" for i in range(1, 7)}, "Decision coverage incomplete")
    for task in manifest["tasks"]:
        require(task["status"] == "planned", "Task must remain planned")
        require(set(task["decisions"]) <= decisions, "Unknown decision")
    section = plan.split("## 7.", 1)[1].split("## 8.", 1)[0]
    table_tasks = {}
    task_outputs = {}
    for line in section.splitlines():
        if re.match(r"^\| [A-Z]\d{2} \|", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            task_id, owner, deliverable, depends = cells
            require(task_id not in table_tasks, "Duplicate Markdown task")
            table_tasks[task_id] = set(re.findall(r"[A-Z]\d{2}", depends))
            task_outputs[task_id] = {"owner": owner, "deliverable": deliverable}
            require(bool(owner) and bool(deliverable), "Task owner/output missing")
    require(set(table_tasks) == task_ids, "Markdown/manifest task mismatch")
    for task in manifest["tasks"]:
        require(table_tasks[task["id"]] == set(task["depends_on"]), "Markdown/manifest dependency mismatch: " + task["id"])
    local_identifiers = set()
    authority_paths = set()
    for row in coverage:
        item_id = row["id"]
        match = re.search(r"^### " + item_id + r" - .*?(?=^### [HB]\d{2} -|^## 5\.)", plan, re.M | re.S)
        require(match is not None, "Finding specification missing: " + item_id)
        body = match.group(0)
        require("Dado" in body or "Dada" in body, "BDD precondition missing")
        require("cuando" in body.lower() and "entonces" in body.lower(), "BDD transition/result missing: " + item_id)
        for key in ("functional_id", "acceptance_id", "scenario_id", "test_id"):
            require(row[key] in body, "Missing spec link: " + row[key])
            require(row[key] not in local_identifiers, "Duplicate local identifier")
            local_identifiers.add(row[key])
        require(bool(row["task_ids"]) and set(row["task_ids"]) <= task_ids, "Missing or unknown task mapping")
        task_text = body.split("**Tareas:**", 1)[1].split(".", 1)[0]
        declared_tasks = set(re.findall(r"[A-Z]\d{2}", task_text))
        for prefix, first, last in re.findall(r"([A-Z])(\d{2})-[A-Z](\d{2})", task_text):
            declared_tasks.update(f"{prefix}{number:02d}" for number in range(int(first), int(last) + 1))
        require(declared_tasks == set(row["task_ids"]), "Finding task mapping differs from manifest: " + item_id)
        require(row["status"] == "planned", "Coverage must remain planned")
        for relative in row["authority_paths"]:
            require((source_root / relative).is_file(), "Authoritative source missing: " + relative)
            authority_paths.add(relative)
    waves = graph_waves(manifest["tasks"])
    # Negative controls prove the checker rejects structural errors.
    invalid_graphs = [
        [{"id": "A", "depends_on": ["Z"]}],
        [{"id": "A", "depends_on": ["B"]}, {"id": "B", "depends_on": ["A"]}],
        [{"id": "A", "depends_on": []}, {"id": "A", "depends_on": []}],
    ]
    for invalid in invalid_graphs:
        try:
            graph_waves(invalid)
        except ValueError:
            pass
        else:
            raise ValueError("Graph negative control failed")
    reference = verify_reference()
    backlog = []
    for task in manifest["tasks"]:
        backlog.append({"id": task["id"], **task_outputs[task["id"]], "depends_on": task["depends_on"], "decisions": task["decisions"], "coverage": [row["id"] for row in coverage if task["id"] in row["task_ids"]], "status": "planned"})
    return {
        "status": "plan_integrity_verified_not_implementation",
        "baseline": manifest["baseline"],
        "findings": 18, "gaps": 5, "tasks": len(task_ids), "decision_cards": len(decisions),
        "local_traceability_links": len(local_identifiers), "authority_paths_checked": len(authority_paths),
        "dependency_waves_no_duration_assumed": waves, "negative_graph_controls": len(invalid_graphs),
        "reference_arithmetic": reference,
        "backlog": backlog,
        "runtime_tests": "not_run_this_planning_change", "production": "not_touched",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.source_root.resolve(), Path(__file__).resolve().parent)
    serialized = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
        with (args.output.parent / "backlog.csv").open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(["tarea", "responsable", "entregable", "dependencias", "decisiones", "hallazgos_brechas", "estado"])
            for task in result["backlog"]:
                writer.writerow([task["id"], task["owner"], task["deliverable"], ",".join(task["depends_on"]), ",".join(task["decisions"]), ",".join(task["coverage"]), task["status"]])
    print(serialized)

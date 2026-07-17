"""
field_testing/test_config.py
────────────────────────────
Generate, save, and load structured test configurations for
real-world field deployments.

Each configuration records:
  - test_id, subject_id
  - radar placement (type + coordinates)
  - environment (mattress, bedding, occlusions, room size)
  - recording duration
  - ground-truth source
  - arbitrary notes
"""

from __future__ import annotations
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  SINGLE TEST CONFIG
# ────────────────────────────────────────────────────────────────────

def make_test_config(
    subject_id: str = "subject_01",
    placement: str = "bedside_right",
    placement_coords: Optional[Tuple[float, float, float]] = None,
    mattress: str = "foam",
    bedding: str = "duvet",
    occlusions: Optional[List[str]] = None,
    room_size: str = "medium",
    duration_sec: int = CFG.DEFAULT_RECORDING_DURATION_SEC,
    ground_truth: str = "wearable",
    notes: str = "",
    test_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a single test configuration dictionary.

    Parameters
    ──────────
    subject_id       : unique subject identifier
    placement        : one of ``config.PLACEMENT_TYPES``
    placement_coords : (x, y, z) in metres (None → use defaults)
    mattress         : one of ``config.MATTRESS_TYPES``
    bedding          : one of ``config.BEDDING_TYPES``
    occlusions       : list of strings from ``config.OCCLUSION_TYPES``
    room_size        : "small" | "medium" | "large"
    duration_sec     : planned recording duration
    ground_truth     : "wearable" | "psg" | "manual" | "pseudo"
    notes            : free-text field notes
    test_id          : unique test identifier (auto-generated if None)

    Returns
    ───────
    dict with all fields above plus timestamp and radar coords.
    """
    if test_id is None:
        test_id = uuid.uuid4().hex[:12]

    if placement_coords is None:
        placement_coords = CFG.PLACEMENT_COORDS_DEFAULT.get(
            placement, (0.0, 0.0, 0.70),
        )

    if occlusions is None:
        occlusions = ["none"]

    return {
        "test_id":           test_id,
        "subject_id":        subject_id,
        "timestamp":         datetime.utcnow().isoformat() + "Z",
        "placement":         placement,
        "placement_coords":  list(placement_coords),
        "mattress":          mattress,
        "bedding":           bedding,
        "occlusions":        occlusions,
        "room_size":         room_size,
        "duration_sec":      duration_sec,
        "ground_truth":      ground_truth,
        "notes":             notes,
    }


# ────────────────────────────────────────────────────────────────────
#  BATCH CONFIGURATION GENERATOR
# ────────────────────────────────────────────────────────────────────

def generate_test_configs(
    n_subjects: int = CFG.SYNTHETIC_N_SUBJECTS,
    placements: Optional[List[str]] = None,
    mattresses: Optional[List[str]] = None,
    beddings: Optional[List[str]] = None,
    occlusions_pool: Optional[List[List[str]]] = None,
    room_sizes: Optional[List[str]] = None,
    duration_sec: int = CFG.DEFAULT_RECORDING_DURATION_SEC,
    ground_truth: str = "wearable",
    seed: int = CFG.RANDOM_SEED,
) -> List[Dict[str, Any]]:
    """
    Generate a batch of test configurations covering multiple
    subjects, placements, and environments.

    Produces one config per (subject × placement × environment).

    Parameters
    ──────────
    n_subjects       : number of subjects
    placements       : placement list (default: first N from config)
    mattresses       : mattress types to cycle through
    beddings         : bedding types to cycle through
    occlusions_pool  : list-of-lists; each inner list is a combo
    room_sizes       : room size pool
    seed             : random seed for shuffling

    Returns list of config dicts.
    """
    rng = np.random.RandomState(seed)

    if placements is None:
        placements = CFG.PLACEMENT_TYPES[:CFG.SYNTHETIC_N_PLACEMENTS]
    if mattresses is None:
        mattresses = CFG.MATTRESS_TYPES[:3]
    if beddings is None:
        beddings = CFG.BEDDING_TYPES[:3]
    if occlusions_pool is None:
        occlusions_pool = [["none"], ["pillow_adjacent"],
                           ["side_table"], ["partner_present"]]
    if room_sizes is None:
        room_sizes = CFG.ROOM_SIZES

    configs: List[Dict] = []
    counter = 0

    for subj_idx in range(n_subjects):
        subject_id = f"subject_{subj_idx + 1:02d}"

        # Each subject gets a random subset of environments
        n_envs = min(CFG.SYNTHETIC_N_ENVS, len(mattresses))
        mat_idx = rng.choice(len(mattresses), size=n_envs, replace=False)
        bed_idx = rng.choice(len(beddings), size=n_envs, replace=False)

        for env_i in range(n_envs):
            mattress = mattresses[mat_idx[env_i]]
            bedding = beddings[bed_idx[env_i]]
            occ = occlusions_pool[rng.randint(len(occlusions_pool))]
            room = room_sizes[rng.randint(len(room_sizes))]

            for pl in placements:
                counter += 1
                cfg = make_test_config(
                    subject_id=subject_id,
                    placement=pl,
                    mattress=mattress,
                    bedding=bedding,
                    occlusions=occ,
                    room_size=room,
                    duration_sec=duration_sec,
                    ground_truth=ground_truth,
                    test_id=f"FT{counter:04d}",
                )
                configs.append(cfg)

    return configs


# ────────────────────────────────────────────────────────────────────
#  SAVE / LOAD
# ────────────────────────────────────────────────────────────────────

def save_configs(
    configs: List[Dict],
    output_dir: str,
    filename: str = "field_test_configs.json",
) -> str:
    """Save config list to JSON.  Returns file path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        json.dump(configs, f, indent=2)
    return path


def load_configs(path: str) -> List[Dict]:
    """Load a previously saved config JSON file."""
    with open(path) as f:
        return json.load(f)


def save_configs_csv(
    configs: List[Dict],
    output_dir: str,
    filename: str = "field_test_configs.csv",
) -> str:
    """Save configs to a flat CSV (one row per test).  Returns path."""
    import csv

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)

    if not configs:
        return path

    flat_keys = [
        "test_id", "subject_id", "timestamp", "placement",
        "mattress", "bedding", "room_size", "duration_sec",
        "ground_truth", "notes",
    ]
    extra_keys = ["placement_coords", "occlusions"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=flat_keys + extra_keys)
        writer.writeheader()
        for c in configs:
            row = {k: c.get(k, "") for k in flat_keys}
            row["placement_coords"] = json.dumps(c.get("placement_coords", []))
            row["occlusions"] = json.dumps(c.get("occlusions", []))
            writer.writerow(row)

    return path

"""Loads the Ward 12 scenario files once and keeps them in memory."""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SCENARIO_DIR = DATA_DIR / "scenario"


def _load(name):
    return json.loads((SCENARIO_DIR / name).read_text(encoding="utf-8"))


@lru_cache
def ward():
    return _load("ward.json")


@lru_cache
def roads():
    return _load("roads.json")


@lru_cache
def landmarks():
    return _load("landmarks.json")


@lru_cache
def households():
    return _load("households.json")


@lru_cache
def teams():
    return _load("teams.json")


@lru_cache
def camps():
    return _load("camps.json")


@lru_cache
def sensors():
    return _load("sensors.json")


def landmark_by_id(landmark_id):
    return next((l for l in landmarks() if l["id"] == landmark_id), None)


def household_by_id(household_id):
    return next((h for h in households() if h["id"] == household_id), None)


def camp_by_id(camp_id):
    return next((c for c in camps() if c["id"] == camp_id), None)

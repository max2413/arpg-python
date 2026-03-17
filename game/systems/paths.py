"""Shared repository-relative paths for static data and runtime state."""

import os


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
RUNTIME_DIR = os.path.join(REPO_ROOT, "runtime")
SAVE_DIR = os.path.join(RUNTIME_DIR, "saves")
CACHE_DIR = os.path.join(RUNTIME_DIR, "cache")


def data_path(*parts):
    return os.path.join(DATA_DIR, *parts)


def runtime_path(*parts):
    return os.path.join(RUNTIME_DIR, *parts)


def save_path(*parts):
    return os.path.join(SAVE_DIR, *parts)


def cache_path(*parts):
    return os.path.join(CACHE_DIR, *parts)

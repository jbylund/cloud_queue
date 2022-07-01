#!/bin/bash
python -m pre_commit run --all-files ||
    python -m pre_commit run --all-files

#!/bin/bash

uv run pyinstaller --onefile \
                   --name multi-ai \
                   --paths src \
                   src/run.py
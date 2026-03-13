#!/bin/bash

uv run pyinstaller --onefile --windowed \
                   --name multi-ai \
                   --paths src \
                   src/run_gui.py
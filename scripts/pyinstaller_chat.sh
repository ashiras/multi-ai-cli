#!/bin/bash

uv run pyinstaller --onefile \
                   --name portable-chat \
                   --paths src \
                   src/run_chat.py
"""
Main entry point script to execute the multi-ai-gui.
"""

import warnings

from multi_ai_gui.main import main

# Filter specific warnings before execution
warnings.filterwarnings(
    "ignore", message=".*Unable to find acceptable character detection dependency.*"
)

if __name__ == "__main__":
    main()

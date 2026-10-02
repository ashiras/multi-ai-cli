"""
Main entry point script to execute the portable_agent_chat.
"""

import warnings

from portable_agent_chat.main import main

# Filter specific warnings before execution
warnings.filterwarnings(
    "ignore", message=".*Unable to find acceptable character detection dependency.*"
)

if __name__ == "__main__":
    main()

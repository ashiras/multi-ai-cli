#!/bin/bash

uv run multi-ai << 'EOF'
@sh "echo '<p>Hello World</p>'" -w raw.html
@gpt "Extract the text from this HTML" -r raw.html -w text.txt
@claude "Translate this text into Japanese" -r text.txt
exit
EOF

echo "Scenario test complete!"
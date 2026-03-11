@gpt "Organize this issue into a specification" -r issue.md -w spec.md
-> @pause
-> @claude "Write a detailed design based on spec.md" -r spec.md -w design.md
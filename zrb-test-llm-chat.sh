#!/bin/bash
set -e

# Create a temporary directory for the test
TMP_DIR=$(mktemp -d)

# Ensure the temporary directory is cleaned up on exit
trap 'rm -rf "$TMP_DIR"' EXIT

echo "🧪 Starting rigorous test in temporary directory: $TMP_DIR"


# Set environment variables to trigger memory management
export _SUMMARIZATION_TOKEN_THRESHOLD=${ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD}
export ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD=3000

(
    echo "Hello. For this session, my project's codename is 'Bluebird'. We will be working in the directory '$TMP_DIR'. Please create a file in that directory named 'file1.txt' with the content 'This is the first file.'"

    echo "Great. Now, please list the files in the '$TMP_DIR' directory."

    echo "Okay, please delete '$TMP_DIR/file1.txt'."

    echo "Now, let's do some software engineering tasks. Please create a python 'Todo' application in '$TMP_DIR/todo.py'. It should have a class named 'Todo' with methods to add, remove, and list tasks."

    echo "Excellent. Now, create a unittest file for it at '$TMP_DIR/test_todo.py'."

    echo "Great. Now, please run the tests in '$TMP_DIR/test_todo.py'."

    echo "Perfect. Lastly, create a Mermaid.js class diagram for the 'Todo' application and save it to '$TMP_DIR/diagram.mmd'."

    echo "What is the current weather at my current location?"

    echo "Fetch some news from news.ycombinator.com"

    echo "Who am I?"

    echo "What was the project's codename I mentioned earlier?"

    echo "Finally, show the content of every file in '$TMP_DIR'"

    echo "/bye"
) | zrb llm chat "Hello, my name is Go Frendi, a software engineer" --start-new

# Unset the environment variables to clean up
export ZRB_LLM_SUMMARIZATION_TOKEN_THRESHOLD=${_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD}

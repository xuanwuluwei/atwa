#!/bin/bash
# Post-tool-use hook: run related tests when a test file or source file is edited.
# Called by Claude Code settings.json PostToolUse hook.
# Usage: bash .claude/hooks/test_related.sh $CLAUDE_TOOL_INPUT_FILE

FILE="$1"

if [[ -z "$FILE" ]]; then
    exit 0
fi

# Only check files inside the project directory
if [[ "$FILE" != /Users/jca/atwa/* ]]; then
    exit 0
fi

# If the edited file is a test file, run it directly
if [[ "$FILE" == tests/* || "$FILE" == */test_*.py ]]; then
    echo "=== pytest $(basename "$FILE") ==="
    python -m pytest "$FILE" -q 2>&1
    exit $?
fi

# If the edited file is a source file, try to find and run the corresponding test
if [[ "$FILE" == *.py ]]; then
    # e.g. config/loader.py -> tests/test_config.py (heuristic: strip dir, find by module name)
    MODULE=$(basename "$FILE" .py)
    # Skip __init__ and private modules
    if [[ "$MODULE" == "__init__" || "$MODULE" == _* ]]; then
        # Try parent directory name instead
        PARENT=$(basename "$(dirname "$FILE")")
        TEST_FILE="tests/test_${PARENT}.py"
    else
        PARENT=$(basename "$(dirname "$FILE")")
        # Try tests/test_<parent>.py first (matches current project pattern)
        TEST_FILE="tests/test_${PARENT}.py"
        if [[ ! -f "$TEST_FILE" ]]; then
            TEST_FILE="tests/test_${MODULE}.py"
        fi
    fi

    if [[ -f "$TEST_FILE" ]]; then
        echo "=== pytest $(basename "$TEST_FILE") (related to $(basename "$FILE")) ==="
        python -m pytest "$TEST_FILE" -q 2>&1
    fi
fi

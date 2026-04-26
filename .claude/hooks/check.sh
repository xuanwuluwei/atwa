#!/bin/bash
# Post-tool-use hook: lint + type check after each file write/edit.
# Called by Claude Code settings.json PostToolUse hook.
# Usage: bash .claude/hooks/check.sh $CLAUDE_TOOL_INPUT_FILE

FILE="$1"

if [[ -z "$FILE" ]]; then
    echo "check.sh: no file path provided, skipping"
    exit 0
fi

# Only check files inside the project directory
if [[ "$FILE" != /Users/jca/atwa/* ]]; then
    exit 0
fi

if [[ "$FILE" == *.py ]]; then
    echo "=== ruff check $(basename "$FILE") ==="
    ruff check "$FILE" 2>&1
    RUFF_EXIT=$?
    if [ $RUFF_EXIT -ne 0 ]; then
        echo "ruff found issues — fix before proceeding"
    fi

    echo "=== mypy $(basename "$FILE") ==="
    python -m mypy "$FILE" 2>&1
    MYPY_EXIT=$?
    if [ $MYPY_EXIT -ne 0 ]; then
        echo "mypy found issues — fix before proceeding"
    fi
elif [[ "$FILE" == *.toml ]]; then
    # Validate TOML can be parsed by the config loader
    echo "=== validating $(basename "$FILE") ==="
    python -c "
import tomllib
from pathlib import Path
tomllib.loads(Path('$FILE').read_text())
print('TOML valid')
" 2>&1
elif [[ "$FILE" == *.ts || "$FILE" == *.tsx ]]; then
    # Frontend not yet created, placeholder for when it exists
    if command -v tsc &>/dev/null; then
        echo "=== tsc --noEmit ==="
        tsc --noEmit 2>&1
    fi
    if command -v eslint &>/dev/null; then
        echo "=== eslint $(basename "$FILE") ==="
        eslint "$FILE" 2>&1
    fi
fi

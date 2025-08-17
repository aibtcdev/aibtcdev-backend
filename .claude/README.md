# Claude Code Hooks Configuration

This directory contains Claude Code hooks that automatically run ruff linting and formatting on Python files.

## Hooks Overview

### `hooks.json` - Main Hooks Configuration

1. **user-prompt-submit-hook**: Runs comprehensive Python checks when you submit prompts
   - Checks all Python files in the `app/` directory
   - Runs ruff linting
   - Runs typos check (if available)

2. **file-edit-hook**: Runs ruff on edited Python files
   - Automatically fixes issues with `ruff check --fix`
   - Formats code with `ruff format`
   - Only runs on `.py` files

3. **tool-use-hook**: Triggers when Write/Edit/MultiEdit tools are used
   - Auto-fixes and formats Python files
   - Provides clear success/failure feedback

4. **pre-commit-hook**: Runs before git commits
   - Full ruff check on all files
   - Ensures code formatting is correct
   - Blocks commits if issues are found

### `ruff-hooks.json` - Simplified Configuration

Alternative, simpler hook configuration focused specifically on ruff.

## Environment Variables Available

Claude Code provides these environment variables to hooks:

- `$CLAUDE_FILE_PATH`: Path to the file being edited
- `$CLAUDE_TOOL_NAME`: Name of the tool being used (Write, Edit, etc.)

## Configuration

All hooks use:
- **timeout**: 10-20 seconds depending on complexity
- **working_directory**: Project root (`.`)
- **enabled**: `true` by default

## Customization

To disable a hook, set `"enabled": false` in the configuration.

To modify commands, update the `"command"` field for any hook.

## Requirements

- `ruff` must be installed and available in PATH
- `typos` is optional but recommended
- Bash shell environment

## Testing

Test the configuration by:
1. Editing a Python file (should trigger file-edit-hook)
2. Submitting a prompt (should trigger user-prompt-submit-hook)
3. Making a git commit (should trigger pre-commit-hook)

## Troubleshooting

If hooks aren't working:
1. Check that ruff is installed: `ruff --version`
2. Verify hooks.json syntax is valid
3. Check Claude Code settings for hooks configuration
4. Ensure working directory permissions are correct
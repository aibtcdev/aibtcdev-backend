# Simple Workflows Prompts

This directory contains all system and user prompts used by the simplified workflow system, organized for easier management and maintenance.

## Structure

```
prompts/
├── __init__.py          # Package initialization and exports
├── loader.py            # Prompt loading utilities
├── evaluation.py        # Evaluation workflow prompts
├── metadata.py          # Metadata generation prompts
├── recommendation.py    # Recommendation generation prompts
└── README.md           # This documentation
```

## Usage

### Direct Import

You can import prompts directly from the prompts package:

```python
from app.services.ai.simple_workflows.prompts import (
    EVALUATION_SYSTEM_PROMPT,
    EVALUATION_USER_PROMPT_TEMPLATE,
    METADATA_SYSTEM_PROMPT,
    RECOMMENDATION_SYSTEM_PROMPT,
)
```

### Using the Prompt Loader

For more flexible prompt management, use the prompt loader:

```python
from app.services.ai.simple_workflows.prompts import (
    load_prompt, 
    get_all_prompts, 
    get_available_prompt_types
)

# Load specific prompts
system_prompt = load_prompt("evaluation", "system")
user_template = load_prompt("metadata", "user_template")

# Get all prompts for a workflow type
all_eval_prompts = get_all_prompts("evaluation")

# Discover what prompt types are available
available_types = get_available_prompt_types()
# Returns: ['evaluation', 'metadata', 'recommendation']
```

## Prompt Organization

### Evaluation Prompts (`evaluation.py`)
- `EVALUATION_SYSTEM_PROMPT`: Comprehensive evaluation criteria and instructions
- `EVALUATION_USER_PROMPT_TEMPLATE`: Template for evaluation requests

### Metadata Prompts (`metadata.py`)
- `METADATA_SYSTEM_PROMPT`: Instructions for generating titles, summaries, and tags
- `METADATA_USER_PROMPT_TEMPLATE`: Template for metadata generation requests

### Recommendation Prompts (`recommendation.py`)
- `RECOMMENDATION_SYSTEM_PROMPT`: Strategic proposal recommendation guidelines
- `RECOMMENDATION_USER_PROMPT_TEMPLATE`: Template for recommendation requests

## Best Practices

### Adding New Prompts

The system automatically discovers new prompt modules! Just follow the naming convention:

1. **Create a new prompt file** for your workflow type (e.g., `analysis.py`)
2. **Define constants** using the naming convention:
   - `{TYPE}_SYSTEM_PROMPT` for system prompts
   - `{TYPE}_USER_PROMPT_TEMPLATE` for user templates
   - Any other constants with `PROMPT` or `TEMPLATE` in the name
3. **That's it!** The loader automatically discovers your prompts

Example `analysis.py`:
```python
"""Analysis prompts for data analysis workflows."""

ANALYSIS_SYSTEM_PROMPT = """You are an expert data analyst..."""

ANALYSIS_USER_PROMPT_TEMPLATE = """Analyze this data:

**DATA:**
{data_content}

**ANALYSIS TYPE:**
{analysis_type}
"""

# Optional: Additional prompts are auto-discovered too
ANALYSIS_SUMMARY_TEMPLATE = """Summarize the analysis results..."""
```

No need to modify `__init__.py` or `loader.py` - it just works!

### Modifying Existing Prompts

1. **Edit the appropriate prompt file** (don't modify the original workflow files)
2. **Test your changes** thoroughly with the affected workflows
3. **Update documentation** if prompt structure or parameters change
4. **Consider backward compatibility** if other systems depend on the prompts

### Prompt Template Variables

When creating user prompt templates, use descriptive variable names that match the function parameters:

```python
USER_PROMPT_TEMPLATE = """Analyze this proposal:

**PROPOSAL:**
{proposal_content}

**DAO MISSION:**
{dao_mission}

**CONTEXT:**
{additional_context}
"""
```

## Migration Notes

This prompts package was created by extracting hardcoded prompts from:
- `evaluation.py` - `DEFAULT_SYSTEM_PROMPT` and `DEFAULT_USER_PROMPT_TEMPLATE`
- `metadata.py` - `system_content` from `create_chat_messages()`
- `recommendation.py` - `system_content` from `create_chat_messages()`

The workflow files now import these prompts instead of defining them inline, making prompt management centralized and easier to maintain.

## Key Features

✅ **Dynamic Discovery**: Automatically finds new prompt modules without code changes  
✅ **Naming Convention**: Simple `{TYPE}_SYSTEM_PROMPT` / `{TYPE}_USER_PROMPT_TEMPLATE` pattern  
✅ **Caching**: Efficient caching to avoid re-loading prompts  
✅ **Auto-scanning**: Discovers any constants with `PROMPT` or `TEMPLATE` in the name  

## Future Enhancements

Potential improvements to consider:

1. **External Prompt Files**: Load prompts from external text/markdown files
2. **Prompt Versioning**: Support for multiple versions of prompts
3. **Prompt Validation**: Validate prompt templates and variable substitution
4. **Hot-reload**: Reload prompts without restarting the application
5. **Advanced Templates**: More sophisticated templating with conditional logic 
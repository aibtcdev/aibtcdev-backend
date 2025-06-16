# Proposal Evaluation Testing

This document explains the two different approaches for testing proposal evaluations and their corresponding test files.

## Overview

We have two evaluation systems:

1. **Multi-Agent Workflow** (`test_proposal_evaluation.py`) - Uses separate agents for core, financial, historical, social context, and reasoning
2. **Comprehensive Single-Agent** (`test_comprehensive_evaluation.py`) - Uses one agent that does all evaluations in a single LLM pass

## Multi-Agent Workflow (`test_proposal_evaluation.py`)

### How it Works
- **Image Processing Agent**: Processes any images in the proposal
- **Core Context Agent**: Evaluates mission alignment, clarity, feasibility, community benefit
- **Financial Context Agent**: Analyzes financial implications, budget, cost-benefit
- **Historical Context Agent**: Reviews past proposals, precedents, learning from history
- **Social Context Agent**: Assesses community sentiment, social media, discussions
- **Reasoning Agent**: Synthesizes all inputs and makes final decision

### Usage
```bash
# Basic evaluation
python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc"

# With voting
python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \
  --wallet-id "87654321-4321-8765-2109-987654321cba" --auto-vote

# Verbose debugging
python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \
  --debug-level 2
```

### Advantages
- **Specialized Expertise**: Each agent focuses on specific domain knowledge
- **Detailed Analysis**: Deep dive into each evaluation category
- **Transparency**: Clear breakdown of how each score was calculated
- **Modularity**: Easy to modify individual agents without affecting others

### Disadvantages
- **Higher Token Usage**: Multiple LLM calls increase costs
- **Slower Execution**: Sequential agent calls take longer
- **Complexity**: More moving parts, potential for workflow issues
- **Potential Inconsistency**: Different agents might have different "personalities"

## Comprehensive Single-Agent (`test_comprehensive_evaluation.py`)

### How it Works
- **Image Processing**: Still uses separate image processing first
- **Comprehensive Evaluator**: Single agent with massive prompt containing all evaluation criteria
  - Core context evaluation (mission alignment, clarity, feasibility, community benefit)
  - Financial context evaluation (budget analysis, cost-benefit, financial impact)
  - Historical context evaluation (precedent analysis, learning from past proposals)
  - Social context evaluation (sentiment analysis, community discussions)
  - Final reasoning and decision synthesis
- **Single Output**: Returns all scores, summaries, and final decision in one response

### Usage
```bash
# Basic comprehensive evaluation
python test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc"

# With voting
python test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \
  --wallet-id "87654321-4321-8765-2109-987654321cba" --auto-vote

# Compare with multi-agent approach
python test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \
  --compare-with-multi-agent
```

### Advantages
- **Efficiency**: Single LLM call reduces token usage and costs
- **Speed**: Faster execution with one API call
- **Consistency**: Single agent maintains consistent reasoning style
- **Simplicity**: Fewer moving parts, easier to debug

### Disadvantages
- **Prompt Complexity**: Massive prompt might hit context limits
- **Less Specialization**: Single agent may not have deep domain expertise
- **Harder to Debug**: All logic in one black box
- **Potential Overwhelm**: Large prompt might cause agent to miss nuances

## Key Features Comparison

| Feature | Multi-Agent | Comprehensive |
|---------|-------------|---------------|
| **Token Usage** | Higher (5-6 LLM calls) | Lower (1 LLM call) |
| **Execution Time** | Slower | Faster |
| **Specialization** | High (domain experts) | Medium (generalist) |
| **Debugging** | Easier (step by step) | Harder (single output) |
| **Consistency** | Variable | High |
| **Complexity** | High | Low |
| **Modularity** | High | Low |

## Test File Features

### Common Arguments
Both test files support:
- `--proposal-id` (required): UUID of proposal to evaluate
- `--wallet-id`: Wallet for voting (optional)
- `--agent-id`: Agent ID (optional)
- `--dao-id`: DAO ID (optional)
- `--auto-vote`: Enable automatic voting
- `--confidence-threshold`: Minimum confidence for voting (default: 0.7)
- `--debug-level`: 0=normal, 1=verbose, 2=very verbose
- `--evaluation-only`: Never vote, just evaluate

### Comprehensive Test Unique Features
- `--compare-with-multi-agent`: Run both approaches and compare results
- Enhanced output showing evaluation type and efficiency metrics
- Side-by-side comparison of decisions, confidence, and token usage

## Recommendations

### Use Multi-Agent When:
- You need detailed, specialized analysis
- Transparency and explainability are crucial  
- You want to fine-tune individual evaluation aspects
- Token cost is not a primary concern
- You need to audit specific evaluation components

### Use Comprehensive When:
- Speed and efficiency are priorities
- Token costs need to be minimized
- You want consistent reasoning style
- The proposal evaluation pipeline needs to be simple
- You're doing high-volume evaluations

## Example Comparison Output

When using `--compare-with-multi-agent`, you'll see:

```
🔍 Comparison Summary:
   • Decisions Match: ✅ YES
     - Comprehensive: Approve
     - Multi-Agent: Approve
   • Confidence Difference: 0.050
     - Comprehensive: 0.850
     - Multi-Agent: 0.800
   • Token Efficiency: 45.2% savings
     - Comprehensive: 8,240 tokens
     - Multi-Agent: 15,030 tokens
```

This helps you understand:
- Whether both approaches reach the same conclusion
- How confident each approach is
- The efficiency gains of the comprehensive approach

## Files Structure

```
├── test_proposal_evaluation.py          # Multi-agent workflow test
├── test_comprehensive_evaluation.py     # Comprehensive single-agent test
├── services/ai/workflows/
│   ├── proposal_evaluation.py          # Original multi-agent workflow
│   ├── comprehensive_evaluation.py     # New comprehensive workflow
│   └── agents/
│       ├── evaluator.py               # ComprehensiveEvaluatorAgent
│       ├── core_context.py            # Core evaluation agent
│       ├── financial_context.py       # Financial evaluation agent
│       ├── historical_context.py      # Historical evaluation agent
│       ├── social_context.py          # Social evaluation agent
│       └── reasoning.py               # Final reasoning agent
└── README_EVALUATION_TESTS.md          # This documentation
```

Both approaches are valid and serve different use cases. The comprehensive approach is recommended for production use due to its efficiency, while the multi-agent approach is valuable for research, debugging, and cases requiring detailed transparency. 
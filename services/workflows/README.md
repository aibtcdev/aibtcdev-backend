# Workflows Module

This module contains workflow implementations for various AI agent tasks. The primary focus is on providing structured, composable workflows that can coordinate multiple specialized agents.

## Directory Structure

```
services/workflows/
├── agents/                   # Specialized agent implementations
│   ├── core_context.py       # Evaluates proposals against DAO mission and values
│   ├── financial_context.py  # Analyzes financial aspects of proposals
│   ├── historical_context.py # Evaluates proposals against historical context
│   ├── image_processing.py   # Processes images in proposals
│   ├── reasoning.py          # Makes final decisions based on other agents' input
│   └── social_context.py     # Evaluates social/community aspects of proposals
│
├── utils/                    # Shared utilities for workflow support
│   ├── models.py             # Shared Pydantic models
│   ├── state_reducers.py     # State management utilities
│   └── token_usage.py        # Token usage tracking utilities
│
├── base.py                   # Base workflow infrastructure
├── capability_mixins.py      # Capability mixins for agent extensions
├── hierarchical_workflows.py # Hierarchical team workflow infrastructure
├── planning_mixin.py         # Planning capabilities
├── proposal_evaluation.py    # Proposal evaluation workflow
├── vector_mixin.py           # Vector retrieval capabilities
└── web_search_mixin.py       # Web search capabilities
```

## Main Workflows

### Proposal Evaluation Workflow

The `ProposalEvaluationWorkflow` in `proposal_evaluation.py` is a hierarchical workflow that uses multiple specialized agents to evaluate a DAO proposal. The workflow:

1. Processes any images in the proposal
2. Evaluates the proposal against the DAO's mission and values (core context)
3. Evaluates the proposal against historical precedents
4. Analyzes the financial aspects of the proposal
5. Evaluates the social context and community impacts
6. Makes a final decision combining all evaluations

API functions:
- `evaluate_proposal(proposal_id, proposal_data, config)`: Evaluates a proposal
- `evaluate_and_vote_on_proposal(proposal_id, ...)`: Evaluates and automatically votes on a proposal
- `evaluate_proposal_only(proposal_id, ...)`: Evaluates a proposal without voting

## Agents

Each agent in the `agents/` directory specializes in a specific aspect of proposal evaluation:

- `CoreContextAgent`: Evaluates alignment with DAO mission and values
- `HistoricalContextAgent`: Evaluates against past proposals and decisions
- `FinancialContextAgent`: Analyzes budget, costs, and financial impact
- `SocialContextAgent`: Evaluates community impact and social context
- `ReasoningAgent`: Makes the final decision based on all evaluations
- `ImageProcessingNode`: Handles image extraction and processing

## Utilities

The `utils/` directory contains shared utilities:

- `state_reducers.py`: Contains functions for managing state in workflows
- `token_usage.py`: Provides the `TokenUsageMixin` for tracking LLM token usage
- `models.py`: Contains shared Pydantic models like `AgentOutput` and `FinalOutput` 
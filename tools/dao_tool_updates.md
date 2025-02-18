# DAO Tool Response Format Updates

We need to update all DAO tools to consistently use the new DAOToolResponse format that matches the Bun script ToolResponse type:

```typescript
export type ToolResponse<T> = {
  success: boolean;
  message: string;
  data?: T;
};
```

## Files to Update

### Charter Tools
- [x] tools/dao_ext_charter.py
  - GetCurrentDaoCharterTool
  - GetCurrentDaoCharterVersionTool 
  - GetDaoCharterTool

### Treasury Tools
- [x] tools/dao_ext_treasury.py
  - GetAllowedAssetTool
  - IsAllowedAssetTool

### Payments & Invoices Tools
- [x] tools/dao_ext_payments_invoices.py
  - GetInvoiceTool
  - GetResourceTool
  - GetResourceByNameTool
  - PayInvoiceTool
  - PayInvoiceByResourceNameTool

### Bank Account Tools
- [x] tools/dao_ext_bank_account.py
  - GetAccountTermsTool
  - DepositSTXTool
  - WithdrawSTXTool

### Action Proposals Tools
- [x] tools/dao_ext_action_proposals.py
  - ProposeActionAddResourceTool
  - ProposeActionAllowAssetTool
  - ProposeActionSendMessageTool
  - ProposeActionSetAccountHolderTool
  - ProposeActionSetWithdrawalAmountTool
  - ProposeActionSetWithdrawalPeriodTool
  - ProposeActionToggleResourceTool
  - VoteOnActionProposalTool
  - ConcludeActionProposalTool
  - GetLiquidSupplyTool
  - GetProposalTool
  - GetTotalVotesTool
  - GetVotingConfigurationTool
  - GetVotingPowerTool

## Changes Made

All tools have been updated to use the DAOToolResponse format:

1. Error responses now use:
```python
result.get("message", "Unknown error"),
result.get("data")
```

2. Success responses now use:
```python
result.get("message", "Operation successful"),
result.get("data")
```

## Progress Tracking

- [x] Base DAO tools updated
- [x] Onchain messaging tools updated
- [x] Charter tools updated
- [x] Treasury tools updated
- [x] Payments & Invoices tools updated
- [x] Bank Account tools updated
- [x] Action Proposals tools updated

✅ All tools have been updated to use the new DAOToolResponse format

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
- [ ] tools/dao_ext_charter.py
  - GetCurrentDaoCharterTool
  - GetCurrentDaoCharterVersionTool 
  - GetDaoCharterTool

### Treasury Tools
- [ ] tools/dao_ext_treasury.py
  - GetAllowedAssetTool
  - IsAllowedAssetTool

### Payments & Invoices Tools
- [ ] tools/dao_ext_payments_invoices.py
  - GetInvoiceTool
  - GetResourceTool
  - GetResourceByNameTool
  - PayInvoiceTool
  - PayInvoiceByResourceNameTool

## Changes Needed

For each tool's _deploy method, update:

1. Error responses from:
```python
result.get("error", "Unknown error"),
result.get("output", "")
```
to:
```python
result.get("message", "Unknown error"),
result.get("data")
```

2. Success responses from:
```python
result["output"],
{"raw_result": result}
```
to:
```python
result.get("message", "Operation successful"),
result.get("data")
```

## Progress Tracking

- [x] Base DAO tools updated
- [x] Onchain messaging tools updated
- [ ] Charter tools pending
- [ ] Treasury tools pending
- [ ] Payments & Invoices tools pending

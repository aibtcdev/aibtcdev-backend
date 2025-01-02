# Twitter DAO Bot Guide

## Overview
The Twitter bot (@aibtcdevagent) is primarily focused on DAO creation while offering additional blockchain utilities. This guide explains how to interact with the bot and create your own DAO.

## Creating a DAO

### Simple Format
```
@aibtcdevagent create dao MyDAO
```
The bot will analyze your Twitter profile and recent tweets to suggest appropriate DAO parameters.

### Detailed Format
```
@aibtcdevagent create dao
name: Tiger Conservation
symbol: TIGER
supply: 500M
mission: Protecting wild tigers through blockchain technology
```

### Parameters
- `name`: Your DAO's full name (max 50 chars)
- `symbol`: Token symbol (3-5 chars, alphanumeric)
- `supply`: Token supply (21M to 1B)
- `mission`: DAO's mission statement (max 280 chars)

## Rate Limits
- Weekly DAO creation limit: 1,500
- Public access: Disabled (whitelist only)
- Check status: `@aibtcdevagent status`

## Additional Features

### Wallet Operations
- Check balance: `@aibtcdevagent balance`
- View address: `@aibtcdevagent address`
- Send STX: `@aibtcdevagent send 100 STX to SP2PABAF9FTAJYNFZH93XENAJ8FVY99RRM50D2JG9`

### Market Data
- Price history: `@aibtcdevagent price STX`
- Token info: `@aibtcdevagent info TIGER`

### Transaction Status
- Check tx: `@aibtcdevagent tx 0x123...`

## Best Practices
1. Use clear, descriptive DAO names
2. Keep mission statements concise
3. Choose memorable token symbols
4. Set reasonable token supplies

## Support
- Documentation: https://daos.btc.us/guide
- Help: `@aibtcdevagent help`
- Status: `@aibtcdevagent status`

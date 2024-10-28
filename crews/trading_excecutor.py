import inspect
from typing import Dict
from crewai import Agent, Task
from crewai_tools import tool, Tool
from textwrap import dedent
from lib.crews import AIBTC_Crew
from tools.bun import BunScriptRunner


class TokenTradingExecutorCrew(AIBTC_Crew):
    def __init__(self):
        super().__init__(
            "Token Trading Executor",
            "This crew executes Stacks cryptocurrency token trades based on trading signals provided by the Token Trading Analyzer crew. Argument for this is the token name.",
        )

    def setup_agents(self):
        # Agent for pulling market data
        trading_agent = Agent(
            role="Token Trader",
            goal="Execute trades based on trading signals provided by the Token Trading Analyzer crew.",
            tools=[
                AgentTools.execute_buy_trade,
                AgentTools.execute_sell_trade,
                AgentTools.get_wallet_balance,
            ],
            backstory=dedent(
                f"""
                You are a specialized token trader with access to various decentralized exchanges (DEXs).
                Your primary responsibility is to execute trades based on trading signals provided by the Token Trading Analyzer crew.
                You are responsible for ensuring accurate and timely execution of trades, and for managing position sizes to optimize profits.
                """
            ),
            verbose=True,
        )
        self.add_agent(trading_agent)

    def setup_tasks(self, analysis_results, crypto_symbol):

        know_about_analysis_results = Task(
            description=f"Heres the token analysis {analysis_results}.",
            expected_output="Details about the analysis on how to execute the trade. From and To token",
            agent=self.agents[0],  # market_data_agent
        )
        self.add_task(know_about_analysis_results)

        get_my_wallet_balance_task = Task(
            description=f"This task will retrieve the current balance of the wallet for the specified cryptocurrency. Get the current balance of the wallet for {crypto_symbol}.",
            expected_output="A dictionary with details about the wallet balance.",
            agent=self.agents[0],  # market_data_agent
        )
        self.add_task(get_my_wallet_balance_task)

        execute_trade_task = Task(
            description=dedent(
                f"""
                Execute a trade for {crypto_symbol} based on trading signals provided by the Token Trading Analyzer crew.
                This task will execute a trade for the specified cryptocurrency based on trading signals provided by the Token Trading Analyzer crew.
                The trade will be executed with position size management to optimize profits. Only ever do 1 STX when buying and when selling sell all of what i own.
                """
            ),
            expected_output="A dictionary with details about the executed trade.",
            agent=self.agents[0],  # market_data_agent
        )
        self.add_task(execute_trade_task)

    @staticmethod
    def get_task_inputs():
        return ["crypto_symbol"]

    @classmethod
    def get_all_tools(cls):
        return AgentTools.get_all_tools()


# Agent Tools
class AgentTools:
    @staticmethod
    @tool("Execute Buy Trade")
    def execute_buy_trade(amount: str, token: str) -> Dict:
        """Execute a market buy order with position size management. Tokens are formatted as token-${token_symbol}. Ex. token-stx token-welsh token-alex"""
        try:
            result = BunScriptRunner.bun_run(
                "stacks-bitflow", "exec-swap.ts", "0.04", amount, "token-stx", token
            )

            return {
                "status": "success",
                "token": token,
                "amount": amount,
                "transaction_details": result,
            }

        except Exception as e:
            raise Exception(f"Buy trade execution error: {str(e)}")

    @staticmethod
    @tool("Execute Sell Trade")
    def execute_sell_trade(amount: str, token: str) -> Dict:
        """Execute a market sell order with position size management. Tokens are formatted as token-${token_symbol}. Ex. token-stx token-welsh token-alex"""
        try:
            result = BunScriptRunner.bun_run(
                "stacks-bitflow", "exec-swap.ts", "0.04", amount, token, "token-stx"
            )

            return {
                "status": "success",
                "token": token,
                "amount": amount,
                "transaction_details": result,
            }

        except Exception as e:
            raise Exception(f"Buy trade execution error: {str(e)}")

    @staticmethod
    @tool("Get Wallet Balance")
    def get_wallet_balance() -> Dict:
        """Get the current balance of the wallet for the tokens."""
        try:
            return BunScriptRunner.bun_run(
                "stacks-wallet",
                "get-my-wallet-balance.ts",
            )

        except Exception as e:
            raise Exception(f"Sell trade execution error: {str(e)}")

    @classmethod
    def get_all_tools(cls):
        members = inspect.getmembers(cls)
        tools = [
            member
            for name, member in members
            if isinstance(member, Tool)
            or (hasattr(member, "__wrapped__") and isinstance(member.__wrapped__, Tool))
        ]
        return tools

import inspect
from crewai import Agent, Task
from crewai_tools import tool, Tool
from textwrap import dedent
from lib.crews import AIBTC_Crew
from lib.velar import VelarApi


class TokenTradingAnalyzerCrew(AIBTC_Crew):
    def __init__(self):
        super().__init__(
            "Token Trading Analyzer",
            "This crew analyzes Stacks cryptocurrency token price history and provides trading signals with a recommendation of either 'Buy', 'Sell', or 'Hold'. Argument for this is the token name.",
        )

    def setup_agents(self):
        # Agent for pulling market data
        market_data_agent = Agent(
            role="Market Data Retriever",
            goal="Collect historical and real-time price data for the specified cryptocurrency, broken down by Stacks block intervals. Ensure accuracy by retrieving prices from multiple DEXs and identifying anomalies.",
            tools=[
                AgentTools.get_crypto_history,
                AgentTools.get_all_swaps,
            ],
            backstory=(
                "You are a specialized market data retriever with access to various decentralized exchanges (DEXs). "
                "Your primary responsibility is to gather accurate historical and real-time price data, format it into structured datasets, "
                "and provide granular data at the Stacks block level to support trading strategy analysis."
            ),
            verbose=True,
        )
        self.add_agent(market_data_agent)

        # Agent for analyzing trading strategies
        strategy_analyzer_agent = Agent(
            role="Quantitative Trading Strategy Analyzer",
            goal="Analyze recent price trends and perform statistical analysis on historical data to identify trading signals. "
            "Provide actionable recommendations (Hold, Buy, or Sell) based on moving averages, volatility patterns, and volume changes.",
            tools=[],  # Add any specific tools if applicable.
            backstory=(
                "You are a seasoned quantitative trading expert with deep expertise in financial market analysis and strategy development. "
                "You specialize in leveraging various technical indicators, such as moving averages, RSI, and MACD, to identify potential trading signals "
                "and execute profitable strategies. Your analysis is rooted in a thorough examination of price movements and market dynamics over the last 100 or more blocks."
            ),
            verbose=True,  # Set verbose to False to streamline responses.
        )
        self.add_agent(strategy_analyzer_agent)

    def setup_tasks(self, crypto_symbol):
        # Task to retrieve historical volume data
        merge_data_task = Task(
            description="Merges data from the into a single dataset."
            f"Collect the information for token {crypto_symbol} using the tool `Get All Avaliable Token Info`."
            f"Data should include the token pool volume using the tool `Get Token Pool Volume` using the pool_id"
            f"Data should include prices using the tool `Get Token Price History` using the address",
            expected_output=(
                "A structured dataset containing volume history, including fields block height, volume, and price. The dataset should be free of gaps and anomalies, ensuring completeness for accurate analysis."
            ),
            agent=self.agents[0],  # market_data_agent
        )
        self.add_task(merge_data_task)

        # Task to analyze the price data with a trading strategy
        analyze_strategy_task = Task(
            description=(
                f"Analyze the historical price and volume data of {crypto_symbol} over the last 100 blocks to identify trading signals. "
                "Use the following predefined strategies:\n"
                "1. **Trend Analysis**: Evaluate using 50-period and 100-period moving averages to detect short-term and long-term trends.\n"
                "2. **Volatility Analysis**: Calculate standard deviation and identify any sudden price spikes or drops.\n"
                "3. **Volume Analysis**: Check for unusual volume shifts to identify potential breakouts or breakdowns.\n"
                "4. **Support and Resistance Levels**: Identify key support and resistance levels based on price patterns.\n"
                "5. **Momentum Indicators**: Apply RSI and MACD to detect overbought or oversold conditions.\n\n"
                "Based on your analysis, provide a single recommendation: **Buy**, **Sell**, or **Hold**. Include a concise reason for your decision."
            ),
            expected_output="A recommendation of either 'Buy', 'Sell', or 'Hold' in big letters at the very top along with a brief explanation justifying your decision based on the analysis.",
            agent=self.agents[1],  # market_data_agent
        )
        self.add_task(analyze_strategy_task)

    @staticmethod
    def get_task_inputs():
        return ["crypto_symbol"]

    @classmethod
    def get_all_tools(cls):
        return AgentTools.get_all_tools()


# Agent Tools
class AgentTools:
    @staticmethod
    @tool("Get Token Price, Volume, TVL History")
    def get_crypto_history(token_symbol: str):
        """Retrieve historical price data for a specified cryptocurrency symbol."""
        obj = VelarApi()
        token_stx_pools = obj.get_token_stx_pools(token_symbol.upper())
        pool_agg = obj.get_pool_stats_history_agg(token_stx_pools[0]["id"], "month")

        return pool_agg

    @staticmethod
    @tool("Get All Avaliable Token Info")
    def get_all_swaps():
        """Retrieve all available token information from the Velar API."""
        obj = VelarApi()
        tokens = obj.get_tokens()
        return tokens

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

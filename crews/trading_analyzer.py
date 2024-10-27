import inspect
import streamlit as st
from crewai import Agent, Task
from crewai_tools import tool, Tool
from textwrap import dedent
from lib.crews import AIBTC_Crew
import requests


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
                AgentTools.get_crypto_price_history,
                AgentTools.get_all_swaps,
                AgentTools.get_pool_volume,
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
    @tool("Get Token Price History")
    def get_crypto_price_history(token_address: str):
        """Retrieve historical price data for a specified cryptocurrency symbol."""
        url = f"https://api.alexgo.io/v1/price_history/{token_address}?limit=100"
        headers = {
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers)

        if not response.ok:
            raise Exception(
                f"Failed to get token price history: {response.status_text}"
            )

        data = response.json()

        price_history = data.get("prices", [])
        formatted_history = "\n".join(
            f"Block Height: {price['block_height']}, Price: {price['avg_price_usd']}"
            for price in price_history
        )

        return f"Token: {data['token']}\n{formatted_history}"

    @staticmethod
    @tool("Get All Avaliable Token Info")
    def get_all_swaps():
        """Retrieve all swap data from the Alex API and return a formatted string."""
        url = "https://api.alexgo.io/v1/allswaps"
        headers = {
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers)

        if not response.ok:
            raise Exception(f"Failed to get all swaps: {response.status_text}")

        data = response.json()

        formatted_swaps = "\n".join(
            dedent(
                f"""Pool ID: {swap['id']}, Quote: {swap['quote']}, Symbol: {swap['quoteSymbol']}, Address: {swap['quoteId']}"""
            ).strip()
            for swap in data
        )

        return formatted_swaps

    @staticmethod
    @tool("Get Token Pool Volume History")
    def get_pool_volume(pool_token_id: str):
        """Retrieve pool volume data for a specified pool token ID."""
        url = f"https://api.alexgo.io/v1/pool_volume/{pool_token_id}?limit=100"
        headers = {
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers)

        if not response.ok:
            raise Exception(f"Failed to get pool volume: {response.status_text}")

        data = response.json()

        volume_values = data.get("volume_values", [])
        formatted_volume = "\n".join(
            f"Block Height: {volume['block_height']}, Volume: {volume['volume_24h']}"
            for volume in volume_values
        )

        return f"Token: {data['token']}\n{formatted_volume}"

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

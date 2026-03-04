import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy
from datetime import datetime

class AlphaStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1m'
    can_short = True
    
    # 5% hard stop loss
    stoploss = -0.05
    trailing_stop = False
    
    # 5% take profit immediately
    minimal_roi = {
        "0": 0.05
    }

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        Hardcoded leverage of 10.0 for OKX Futures
        """
        return 10.0

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # No indicators needed for immediate buy
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Always trigger a long entry
        dataframe.loc[
            (dataframe['volume'] > 0),
            ['enter_long', 'enter_tag']] = (1, 'immediate_buy')

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Exits will be handled purely by ROI (5%) and Stoploss (5%)
        return dataframe

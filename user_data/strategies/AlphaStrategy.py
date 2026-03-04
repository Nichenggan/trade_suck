import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime


class AlphaStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True
    
    # 50% hard stop loss
    stoploss = -0.5
    trailing_stop = False
    
    minimal_roi = {
        "0": 0.1,     # Take profit at 10%
        "30": 0.05,   # Take profit at 5% after 30 mins
        "60": 0.01    # Take profit at 1% after 60 mins
    }

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        Hardcoded leverage of 50.0 for OKX Futures
        """
        return 50.0

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['rsi'], 30)) &
                (dataframe['volume'] > 0)
            ),
            ['enter_long', 'enter_tag']] = (1, 'rsi_cross_under')
            
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['rsi'], 70)) &
                (dataframe['volume'] > 0)
            ),
            ['enter_short', 'enter_tag']] = (1, 'rsi_cross_over')

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['rsi'], 70)) &
                (dataframe['volume'] > 0)
            ),
            ['exit_long', 'exit_tag']] = (1, 'rsi_overbought')
            
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['rsi'], 30)) &
                (dataframe['volume'] > 0)
            ),
            ['exit_short', 'exit_tag']] = (1, 'rsi_oversold')

        return dataframe

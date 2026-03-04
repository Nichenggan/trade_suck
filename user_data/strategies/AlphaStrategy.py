from freqtrade.strategy import IStrategy
import pandas as pd
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime

class AlphaStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True

    # --- Hyperopt winning parameters ---
    buy_rsi = 28
    sell_rsi = 84

    # ROI parameters:
    minimal_roi = {
        "0": 0.149,
        "15": 0.072,
        "75": 0.032,
        "169": 0
    }

    # Stoploss parameters:
    stoploss = -0.305

    # Trailing stop parameters:
    trailing_stop = True
    trailing_stop_positive = 0.309
    trailing_stop_positive_offset = 0.315
    trailing_only_offset_is_reached = False

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        Hardcoded leverage of 5.0 for OKX Futures
        """
        return 5.0

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Calculate indicators
        """
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Dynamic entry signals using tuned parameters
        """
        # Long entry when RSI crosses below tuned target
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['rsi'], self.buy_rsi)) &
                (dataframe['volume'] > 0)
            ),
            ['enter_long', 'enter_tag']] = (1, 'rsi_oversold_long')
            
        # Short entry when RSI crosses above tuned target
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['rsi'], self.sell_rsi)) &
                (dataframe['volume'] > 0)
            ),
            ['enter_short', 'enter_tag']] = (1, 'rsi_overbought_short')

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        No explicit indicators for exit, relying on ROI and Trailing Stop
        """
        return dataframe

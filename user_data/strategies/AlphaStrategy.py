from freqtrade.strategy import IStrategy, IntParameter
import pandas as pd
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime

class AlphaStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True
    startup_candle_count = 200
    stake_percentage = 0.1

    # --- 策略核心参数 ---
    # 定义杠杆参数，默认5倍，可通过 Hyperopt 优化 (范围 1-10)
    leverage_num = IntParameter(1, 20, default=15, space='buy', optimize=True)
    


    # --- 进场指标参数 ---
    buy_rsi = IntParameter(20, 45, default=30, space='buy')
    sell_rsi = IntParameter(60, 85, default=70, space='sell')

    # --- 止盈止损与移动止盈 (适配 5 倍杠杆) ---
    # 5倍杠杆下给 5m 波动留空间，设 5% 初始止损 (即标的波动 1%)
    stoploss = -0.5 

    # ROI 阶梯止盈
    minimal_roi = {
        "0": 0.1,    
        "10": 0.05,  
        "30": 0.02,  
        "60": 0       
    }

    # 移动止损 (Trailing stop)
    trailing_stop = True
    trailing_stop_positive = 0.02  
    trailing_stop_positive_offset = 0.03 
    trailing_only_offset_is_reached = True

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        """
        仓位管理：每次开仓占当前账户总额 (Total Wallet) 的 10%。
        复利模式开启。
        """
        return self.wallets.get_total_stake_amount() * self.stake_percentage

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        使用参数化杠杆，默认 50 倍
        """
        return float(self.leverage_num.value)

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        计算复杂波段指标：RSI + 布林带 + 威廉指标
        """
        # 1. RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # 2. 布林带 (Bollinger Bands) - 捕捉价格通道边界
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2.2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        
        # 3. 威廉指标 (Williams %R) - 极其灵敏的超买超卖指标，适合吃波段
        dataframe['willr'] = ta.WILLR(dataframe, timeperiod=14)

        # 4. 指数移动平均线 (EMA 200) - 大级别趋势过滤
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        进场逻辑：多重指标共振 + 大级别趋势过滤
        """
        # 做多：价格在 EMA 200 之上 (多头趋势) + 价格跌破布林带下轨 + RSI超卖 + 威廉指标极度超卖
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_200']) &  # 顺大势
                (dataframe['close'] < dataframe['bb_lowerband']) & 
                (dataframe['rsi'] < self.buy_rsi.value) &
                (dataframe['willr'] < -80) &
                (dataframe['volume'] > 0)
            ),
            ['enter_long', 'enter_tag']] = (1, 'swing_bottom_long')
            
        # 做空：价格在 EMA 200 之下 (空头趋势) + 价格突破布林带上轨 + RSI超买 + 威廉指标极度超买
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['ema_200']) &  # 顺大势
                (dataframe['close'] > dataframe['bb_upperband']) & 
                (dataframe['rsi'] > self.sell_rsi.value) &
                (dataframe['willr'] > -20) &
                (dataframe['volume'] > 0)
            ),
            ['enter_short', 'enter_tag']] = (1, 'swing_top_short')

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        离场交由 ROI 和 Trailing stop 自动处理
        """
        return dataframe
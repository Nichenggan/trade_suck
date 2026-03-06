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
    
    # --- 仓位管理参数 ---
    stake_percentage = 0.6      
    min_stake_amount = 10.0     # 最低开仓金额 10 USDT

    # --- 策略核心参数 ---
    leverage_long = IntParameter(1, 10, default=2, space='buy', optimize=False)
    leverage_short = IntParameter(1, 10, default=4, space='buy', optimize=False)
    
    # --- 进场指标参数 (非对称设置) ---
    # 牛市回调很难跌透，所以把 buy_rsi 的默认值提高到 38，范围上限提高到 50
    buy_rsi = IntParameter(25, 50, default=38, space='buy')
    # 熊市反弹猛烈，sell_rsi 保持 70 的高标准
    sell_rsi = IntParameter(60, 85, default=70, space='sell')

    # --- 止盈止损与移动止盈 ---
    stoploss = -0.1 

    minimal_roi = {
        "0": 0.2,    
        "10": 0.1,  
        "30": 0.02,  
        "60": 0       
    }

    trailing_stop = True
    trailing_stop_positive = 0.02  
    trailing_stop_positive_offset = 0.03 
    trailing_only_offset_is_reached = True

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        """
        动态仓位计算
        """
        calculated_stake = self.wallets.get_total_stake_amount() * self.stake_percentage
        final_stake = max(calculated_stake, self.min_stake_amount)
        return final_stake

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        if side == 'long':
            return float(self.leverage_long.value)
        else:
            return float(self.leverage_short.value)

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        计算非对称多空指标
        """
        # 1. RSI & Williams %R
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['willr'] = ta.WILLR(dataframe, timeperiod=14)
        
        # 2. 针对【做空】的布林带 (严格：2.2倍标准差，防插针爆仓)
        bollinger_short = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2.2)
        dataframe['bb_upperband_short'] = bollinger_short['upper']
        
        # 3. 针对【做多】的布林带 (宽松：2.0倍标准差，牛市容易上车)
        bollinger_long = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2.0)
        dataframe['bb_lowerband_long'] = bollinger_long['lower']

        # 4. 趋势过滤均线 (新增 EMA 50 配合 EMA 200 识别大趋势)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        非对称进场逻辑
        """
        # 做多：均线多头排列 (EMA50 > EMA200) + 跌破多头宽松下轨 + RSI/WILLR适度超卖
        # 这样即使K线瞬间砸盘导致 close < ema_200，只要整体均线还在多头，依然能抄到底！
        dataframe.loc[
            (
                (dataframe['ema_50'] > dataframe['ema_200']) & 
                (dataframe['close'] < dataframe['bb_lowerband_long']) & 
                (dataframe['rsi'] < self.buy_rsi.value) &
                (dataframe['willr'] < -75) &  # 从 -80 放宽到 -75
                (dataframe['volume'] > 0)
            ),
            ['enter_long', 'enter_tag']] = (1, 'swing_bottom_long')
            
        # 做空：保持原有的“熊市杀手”逻辑 (大势被压制 + 突破严格上轨 + 极度超买)
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['ema_200']) &  
                (dataframe['close'] > dataframe['bb_upperband_short']) & 
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
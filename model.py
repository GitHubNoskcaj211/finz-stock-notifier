import random
import numpy as np
from sklearn.linear_model import LinearRegression
from matplotlib import pyplot as plt

NUMBER_OF_STOCK_DAYS_IN_YEAR = 260
NUMBER_OF_DAYS_IN_YEAR = 365

class BaseModel:
    def analyze_stock(self, data) -> float:
        raise NotImplementedError()
    
    def sample_num_stocks_to_buy(self, buy_rate: float) -> int:
        if random.random() < buy_rate % 1:
            return 1 + int(buy_rate)
        else:
            return int(buy_rate)

    def get_market_figure(self, open_prices, stock_ticker):
        figure, axis = plt.subplots(1, 1)
        axis.scatter(open_prices.index, open_prices, s = 5)
        axis.set_title(f"Market for {stock_ticker}")
        return figure, axis

    def get_market_trend_figure(self, open_prices, stock_ticker):
        market_trend, score = self.get_market_trend(open_prices)
        x = np.arange(open_prices.shape[0]).reshape(-1, 1)
        predicted_y = market_trend.predict(x)
        figure, axis = self.get_market_figure(open_prices, stock_ticker)
        axis.plot(open_prices.index, predicted_y, color = 'blue', linewidth = 3)
        return figure, axis
    
class RandomModel(BaseModel):
    def __init__(self, buy_rate: float):
        self.name = 'random_model'
        self.buy_rate = buy_rate
        
    def analyze_stock(self, data) -> float:
        return self.buy_rate

# TODO try to add a lump sum model that accounts for monday effect.

# Buy as much as possible every day.
class LumpSumModel(BaseModel):
    def __init__(self, money_to_input: float):
        self.name = 'lump_sum_model'
        self.money_to_input = money_to_input
        
    def analyze_stock(self, data) -> float:
        open_price = data['Open'].iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        buy_rate = self.money_to_input / open_price
        return buy_rate
        
class ConstantDollarRandomModel(BaseModel):
    def __init__(self, annual_money_input: float, spending_cycle: float = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.name = 'constant_dollar_random_model'
        self.annual_money_input = annual_money_input
        self.spending_cycle = spending_cycle
        
    def analyze_stock(self, data) -> float:
        open_price = data['Open'].iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        buy_rate = self.annual_money_input / self.spending_cycle / open_price
        return buy_rate

class LinearRegressionModel(BaseModel):
    def __init__(self, annual_money_input: float, spending_cycle: float = NUMBER_OF_STOCK_DAYS_IN_YEAR, lookback_distance: int = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.name = 'linear_regression_model'
        self.annual_money_input = annual_money_input
        self.spending_cycle = spending_cycle
        self.lookback_distance = lookback_distance
    
    def get_market_trend(self, open_prices):
        y = open_prices.values.reshape(-1, 1)
        num_points = y.shape[0]
        assert num_points == self.lookback_distance, 'Trying to get a market trend with less points than the lookback distance.'
        x = np.arange(num_points).reshape(-1, 1)
        regression = LinearRegression().fit(x,y)
        score = regression.score(x, y)
        return regression, score
    
    def analyze_stock(self, data) -> float:
        open_prices = data['Open'].iloc[-self.lookback_distance:]
        open_price = open_prices.iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        regression, score = self.get_market_trend(open_prices)
        model_open_price = regression.predict([[self.lookback_distance]])[0][0]
        constant_buy_rate = self.annual_money_input / self.spending_cycle / open_price
        scaled_buy_rate = constant_buy_rate * (max(model_open_price, 0) / open_price) ** 4

        market_trend_return = max(model_open_price, 0) / max(regression.intercept_, 0.01)
        if market_trend_return < 1:
            return max(constant_buy_rate, scaled_buy_rate)
        else:
            return scaled_buy_rate
        
class WeightedLinearRegressionModel(BaseModel):
    def __init__(self, annual_money_input: float, spending_cycle: float = NUMBER_OF_STOCK_DAYS_IN_YEAR, lookback_distance: int = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.name = 'weighted_linear_regression_model'
        self.annual_money_input = annual_money_input
        self.spending_cycle = spending_cycle
        self.lookback_distance = lookback_distance
    
    def get_market_trend(self, open_prices):
        y = open_prices.values.reshape(-1, 1)
        num_points = y.shape[0]
        assert num_points == self.lookback_distance, 'Trying to get a market trend with less points than the lookback distance.'
        x = np.arange(num_points).reshape(-1, 1)
        sample_weights = 1 - abs(2 * np.arange(num_points) / num_points - 1) # Linear from 0 -> 1 -> 0.
        regression = LinearRegression().fit(x, y, sample_weights)
        score = regression.score(x, y)
        return regression, score
    
    def analyze_stock(self, data) -> float:
        open_prices = data['Open'].iloc[-self.lookback_distance:]
        open_price = open_prices.iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        regression, score = self.get_market_trend(open_prices)
        model_open_price = regression.predict([[self.lookback_distance]])[0][0]
        constant_buy_rate = self.annual_money_input / self.spending_cycle / open_price
        scaled_buy_rate = constant_buy_rate * (max(model_open_price, 0) / open_price) ** 4

        market_trend_return = max(model_open_price, 0) / max(regression.intercept_, 0.01)
        if market_trend_return < 1:
            return max(constant_buy_rate, scaled_buy_rate)
        else:
            return scaled_buy_rate
        
class LinearDistributionModel(BaseModel):
    def __init__(self, annual_money_input: float, spending_cycle: float = NUMBER_OF_STOCK_DAYS_IN_YEAR, lookback_distance: int = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.name = 'linear_distribution_model'
        self.annual_money_input = annual_money_input
        self.spending_cycle = spending_cycle
        self.lookback_distance = lookback_distance
        
    def analyze_stock(self, data) -> float:
        open_prices = data['Open'].iloc[-self.lookback_distance:]
        range_maximum = max(open_prices)
        range_minimum = min(open_prices)
        open_price = open_prices.iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        constant_buy_rate = self.annual_money_input / self.spending_cycle / open_price
        range_percentile = (open_price - range_minimum) / (range_maximum - range_minimum) if range_maximum > range_minimum else 0.5
        scaled_buy_rate = constant_buy_rate * (1 - range_percentile)
        return scaled_buy_rate
    
class LumpLinearDistributionModel(BaseModel):
    def __init__(self, annual_money_input: float, range_buy_percentage: float = 0.5, lookback_distance: int = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.name = 'lump_linear_distribution_model'
        self.annual_money_input = annual_money_input
        self.range_buy_percentage = range_buy_percentage
        self.lookback_distance = lookback_distance
        
    def analyze_stock(self, data) -> float:
        open_prices = data['Open'].iloc[-self.lookback_distance:]
        range_maximum = max(open_prices)
        range_minimum = min(open_prices)
        open_price = open_prices.iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        constant_buy_rate = self.annual_money_input / open_price
        range_percentile = (open_price - range_minimum) / (range_maximum - range_minimum) if range_maximum > range_minimum else 0.5
        scaled_buy_rate = constant_buy_rate * (1 if range_percentile <= self.range_buy_percentage else 0)
        return scaled_buy_rate
    
class FutureLimitModel(BaseModel):
    def __init__(self, annual_money_input: float, price_decrease: float = 1.0, max_limit_days: int = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.name = 'future_limit_model'
        self.annual_money_input = annual_money_input
        self.max_limit_days = max_limit_days
        self.price_decrease = price_decrease
        
    def analyze_stock(self, data) -> float:
        open_prices = data['Open'].iloc[-(self.max_limit_days + 1):]
        open_price = open_prices.iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        
        previously_completed = [False]
        min_value_encountered = open_prices.iloc[self.max_limit_days - 1]
        for ii in range(self.max_limit_days - 2, -1, -1):
            previously_completed.append(min_value_encountered < open_prices.iloc[ii] * self.price_decrease)
            min_value_encountered = min(min_value_encountered, open_prices.iloc[ii])
        previously_completed.reverse()

        current_completed = [open_prices.iloc[-1] < price * self.price_decrease for price in open_prices.iloc[:-1]]
        orders_to_fill = [current and not previous for current, previous in zip(current_completed, previously_completed)]
        if not previously_completed[0]:
            buy_rate = self.annual_money_input / open_price * (sum(orders_to_fill) + 1)
        else:
            buy_rate = self.annual_money_input / open_price * sum(orders_to_fill)
        return buy_rate
    
class AveragedFutureLimitModel(BaseModel):
    def __init__(self, annual_money_input: float, price_decrease: float = 1.0, max_limit_days: int = NUMBER_OF_STOCK_DAYS_IN_YEAR, spending_cycle: float = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.name = 'averaged_future_limit_model'
        self.annual_money_input = annual_money_input
        self.max_limit_days = max_limit_days
        self.price_decrease = price_decrease
        self.spending_cycle = spending_cycle
        
    def analyze_stock(self, data) -> float:
        open_prices = data['Open'].iloc[-(self.max_limit_days + 1):]
        open_price = open_prices.iloc[-1]
        assert open_price >= 0, 'Model requires an open price >= 0.'
        if open_price == 0:
            return 0
        
        previously_completed = [False]
        min_value_encountered = open_prices.iloc[self.max_limit_days - 1]
        for ii in range(self.max_limit_days - 2, -1, -1):
            previously_completed.append(min_value_encountered < open_prices.iloc[ii] * self.price_decrease)
            min_value_encountered = min(min_value_encountered, open_prices.iloc[ii])
        previously_completed.reverse()

        current_completed = [open_prices.iloc[-1] < price * self.price_decrease for price in open_prices.iloc[:-1]]
        orders_to_fill = [current and not previous for current, previous in zip(current_completed, previously_completed)]
        if not previously_completed[0]:
            buy_rate = self.annual_money_input / self.spending_cycle / open_price * (sum(orders_to_fill) + 1)
        else:
            buy_rate = self.annual_money_input / self.spending_cycle / open_price * sum(orders_to_fill)
        return buy_rate
    
class STDModel(BaseModel):
    def __init__(self, annual_money_input: float, spending_cycle: float = NUMBER_OF_STOCK_DAYS_IN_YEAR, lookback_distance: int = NUMBER_OF_STOCK_DAYS_IN_YEAR):
        self.annual_money_input = annual_money_input
        self.spending_cycle = spending_cycle
        self.lookback_distance = lookback_distance

    def get_avg_and_std(self, column):
        diminishing_avg = 0
        num = column.shape[0]
        slope = 2 / num / num
        for i in range(num):
            diminishing_avg += column[i] * i * slope
        
        diminishing_std = 0
        for i in range(num):
            diminishing_std += (column[i] - diminishing_avg) ** 2 * i * slope
        
        return diminishing_avg, diminishing_std ** 0.5
        
        # return column.mean(), column.std() deprecated for diminishing average

    def analyze_stock(self, data) -> float:
        open_prices = data['Open']
        open_price = open_prices.iloc[-1]        
        mean, std = self.get_avg_and_std(open_prices.iloc[-self.lookback_distance:])
        constant_buy_rate = max(account_balance, self.annual_money_input) / self.spending_cycle / open_price
        scaled_buy_rate = constant_buy_rate * (1 - (open_price - mean) / (std * 3))
        return scaled_buy_rate

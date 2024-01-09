import random
from datetime import date, timedelta, datetime
import pytz
from tqdm import tqdm

from utils import get_data_for_stock, average
from model import BaseModel, RandomModel, ConstantDollarRandomModel, LumpSumModel, FutureLimitModel, AveragedFutureLimitModel, STDModel, LinearDistributionModel, LumpLinearDistributionModel, LinearRegressionModel, WeightedLinearRegressionModel, NUMBER_OF_STOCK_DAYS_IN_YEAR, NUMBER_OF_DAYS_IN_YEAR

from matplotlib import pyplot as plt
import matplotlib
import pandas as pd
import numpy as np
import math

EXAMPLE_STAT_KEY = 'total_annual_roi'
DATE_FORMAT = '%Y-%m-%d'

class SimulationParameters:
    def parse_from_dict(self, dict):
        self.parse_from_inputs(str(dict['stock']), int(dict['random_seed']), datetime.strptime(dict['start_date'], DATE_FORMAT).date(), datetime.strptime(dict['end_date'], DATE_FORMAT).date(), int(dict['start_day_of_cycle']), float(dict['yearly_amount_input']), float(dict['starting_account_balance']), bool(dict['fractional_shares']), int(dict['investment_input_cycle_days']))
        
    def parse_from_inputs(self, stock: str, random_seed: int, start_date: date, end_date: date, start_day_of_cycle: int, yearly_amount_input: float, starting_account_balance: float, fractional_shares: bool, investment_input_cycle_days: int):
        self.stock = stock
        self.random_seed = random_seed
        self.start_date = start_date
        self.end_date = end_date
        self.start_day_of_cycle = start_day_of_cycle
        self.yearly_amount_input = yearly_amount_input
        self.starting_account_balance = starting_account_balance
        self.fractional_shares = fractional_shares
        self.investment_input_cycle_days = investment_input_cycle_days
        
        assert self.start_date <= self.end_date
        assert self.yearly_amount_input > 0
        assert self.starting_account_balance >= 0
        assert self.investment_input_cycle_days > 0
        assert self.start_day_of_cycle < self.investment_input_cycle_days
        
        return self
            
    def convert_to_dict(self):
        return {
            'stock': self.stock,
            'random_seed': self.random_seed,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'start_day_of_cycle': self.start_day_of_cycle,
            'yearly_amount_input': self.yearly_amount_input,
            'starting_account_balance': self.starting_account_balance,
            'fractional_shares': self.fractional_shares,
            'investment_input_cycle_days': self.investment_input_cycle_days,
        }

class Simulator():
    def __init__(self, simulation_parameters: SimulationParameters, data = None, debug: bool = False):
        self.debug = debug
        self.data = data

        self.reset(simulation_parameters)
     
    def reset(self, simulation_parameters: SimulationParameters):
        self.stock = simulation_parameters.stock
        self.random_seed = simulation_parameters.random_seed
        self.start_date = simulation_parameters.start_date
        self.end_date = simulation_parameters.end_date
        self.start_day_of_cycle = simulation_parameters.start_day_of_cycle
        self.yearly_amount_input = simulation_parameters.yearly_amount_input
        self.account_balance = simulation_parameters.starting_account_balance
        self.fractional_shares = simulation_parameters.fractional_shares
        self.investment_input_cycle_days = simulation_parameters.investment_input_cycle_days

        self.model_run_dates = []
        self.cash_over_time = []
        self.total_value_over_time = []
        self.stock_value_over_time = []
        self.purchases = []
        self.desired_dollars_to_buy = []
        self.number_stocks_bought = 0
        self.total_cash_received = 0
        random.seed(self.random_seed)
        
        if self.data is None:
            today_datetime = datetime.now().astimezone(pytz.timezone('US/Eastern'))
            self.data = get_data_for_stock(self.stock, today_datetime)
        assert self.start_date >= self.data.iloc[0].name.date() and self.end_date <= self.data.iloc[-1].name.date()
        
    def display_debug(self, model: BaseModel, fractional_number_to_buy: float, daily_input_data) -> None:
        open_prices = daily_input_data['Open'].iloc[-NUMBER_OF_STOCK_DAYS_IN_YEAR:]
        print(f'Date: {open_prices.index[-1]} | Num to Buy: {fractional_number_to_buy}')
        figure = model.get_market_trend_figure(open_prices, self.stock)
        figure.show()
        
        plt.show()
        input()
        plt.close(figure)
        
    def buy_stocks(self, model: BaseModel, daily_input_data, open_price: float, stock_market_is_open: bool) -> None:
        number_to_buy = model.analyze_stock(daily_input_data)
        if stock_market_is_open:
            self.desired_dollars_to_buy.append(number_to_buy * open_price)
        if self.debug and daily_input_data.shape[0] % 60 == 0:
            self.display_debug(model, number_to_buy, daily_input_data)
        if not self.fractional_shares:
            number_to_buy = model.sample_num_stocks_to_buy(number_to_buy)

        if self.account_balance >= number_to_buy * open_price:
            self.number_stocks_bought += number_to_buy
            self.account_balance -= number_to_buy * open_price
            self.purchases.append([number_to_buy, open_price])
        else:
            number_to_buy = self.account_balance / open_price if open_price > 0 else 0
            if not self.fractional_shares:
                number_to_buy = math.floor(number_to_buy)
            self.number_stocks_bought += number_to_buy
            self.account_balance -= number_to_buy * open_price
            self.purchases.append([number_to_buy, open_price])
        
    def append_nightly_reportings(self, close_price: float) -> None:
        self.cash_over_time.append(self.account_balance)
        self.total_value_over_time.append(self.account_balance + self.number_stocks_bought * close_price)
        self.stock_value_over_time.append(self.number_stocks_bought * close_price)
        
    def simulate(self, model: BaseModel):
        for ii in range((self.end_date - self.start_date).days + 1):
            if (self.investment_input_cycle_days - self.start_day_of_cycle + ii) % self.investment_input_cycle_days == 0:
                input_amount = self.yearly_amount_input * self.investment_input_cycle_days / NUMBER_OF_DAYS_IN_YEAR
                self.account_balance += input_amount
                self.total_cash_received += input_amount
                
            current_date = self.start_date + timedelta(days=ii)
            stock_market_is_open = pd.Timestamp(current_date) in self.data.index
            if current_date.weekday() >= 5:
                continue

            self.model_run_dates.append(current_date)
            daily_input_data = self.data.loc[:current_date]
            open_price = daily_input_data['Open'].iloc[-1]
            close_price = daily_input_data['Close'].iloc[-1]
            
            self.buy_stocks(model, daily_input_data, open_price, stock_market_is_open)
            
            self.append_nightly_reportings(close_price)
    
    def plot(self, log_color_plot = False) -> None:
        evaled_data = self.data.loc[self.start_date:self.end_date]
        figure, axis = plt.subplots(2, 2)
        axis[0, 0].hist([purchase[1] for purchase in self.purchases], edgecolor='black', bins = 100, weights=[purchase[0] for purchase in self.purchases])
        axis[0, 0].set_title("Buy Prices")
        axis[1, 0].plot(self.model_run_dates, self.cash_over_time)
        axis[1, 0].set_title("Cash over time")
        axis[0, 1].plot(self.model_run_dates, self.total_value_over_time)
        axis[0, 1].set_title("Total value over time")
        axis[1, 1].plot(self.model_run_dates, self.stock_value_over_time)
        axis[1, 1].set_title("Stock value over time")
        figure2, axis2 = plt.subplots()
        colors = np.log(np.array(self.desired_dollars_to_buy)) if log_color_plot else self.desired_dollars_to_buy
        scatter = axis2.scatter(evaled_data.index, evaled_data['Open'], c = colors, norm=matplotlib.colors.Normalize(), cmap='viridis', s = 5)
        axis2.set_title(f"Market colored by{' LOG ' if log_color_plot else ' '}money input per day")
        figure2.colorbar(scatter)
        figure.show()
        figure2.show()
        
    def metrics(self):
        purchase_amount_spent = [purchase[0] * purchase[1] for purchase in self.purchases]
        if sum([purchase[0] for purchase in self.purchases]) == 0 or sum(purchase_amount_spent) == 0 or self.total_cash_received == 0 or len(self.cash_over_time) == 0:
            return {}
        metrics = {
            'average_price': sum(purchase_amount_spent) / sum([purchase[0] for purchase in self.purchases]),
            'average_cash': average(self.cash_over_time),
            'end_total_value': self.total_value_over_time[-1],
            'end_stock_value': self.stock_value_over_time[-1],
            'total_cash_received': self.total_cash_received,
            'total_cash_invested': sum(purchase_amount_spent),
            'total_roi': (self.total_value_over_time[-1] - self.total_cash_received) / self.total_cash_received,
            'stock_roi': (self.stock_value_over_time[-1] - sum(purchase_amount_spent)) / sum(purchase_amount_spent),
            'total_annual_roi': (self.total_value_over_time[-1] / self.total_cash_received) ** (NUMBER_OF_DAYS_IN_YEAR / (self.end_date - self.start_date).days) - 1,
            'stock_annual_roi': (self.stock_value_over_time[-1] / sum(purchase_amount_spent)) ** (NUMBER_OF_DAYS_IN_YEAR / (self.end_date - self.start_date).days) - 1,
        }
        assert EXAMPLE_STAT_KEY in metrics.keys()
        return metrics

if __name__ == '__main__':
    stock = 'SPY'
    random_seed = 12
    start_date = date(2000, 1, 1)
    end_date = date(2023, 12, 29)
    start_day_of_cycle = 0
    yearly_amount_input = 5000
    starting_account_balance = 0
    fractional_shares = True
    investment_input_cycle_days = 14
    simulation_parameters = SimulationParameters()
    simulation_parameters.parse_from_inputs(stock, random_seed, start_date, end_date, start_day_of_cycle, yearly_amount_input, starting_account_balance, fractional_shares, investment_input_cycle_days)
    
    # df = pd.read_csv('validation_sets/validation_set.csv')
    # index = 8
    # print(df.iloc[index])
    # yearly_amount_input = df.iloc[index]['yearly_amount_input']
    # investment_input_cycle_days = df.iloc[index]['investment_input_cycle_days']
    # simulation_parameters.parse_from_dict(df.iloc[index])
    
    simulator = Simulator(simulation_parameters, debug = False)
    
    constant_dollar_random_model = ConstantDollarRandomModel(yearly_amount_input, NUMBER_OF_STOCK_DAYS_IN_YEAR)
    lump_sum_model = LumpSumModel(yearly_amount_input)
    # linear_fit_model = LinearRegressionModel(yearly_amount_input, NUMBER_OF_STOCK_DAYS_IN_YEAR, NUMBER_OF_STOCK_DAYS_IN_YEAR)
    linear_distribution_model = LinearDistributionModel(yearly_amount_input, NUMBER_OF_STOCK_DAYS_IN_YEAR, 3)
    lump_linear_distribution_model = LumpLinearDistributionModel(yearly_amount_input, 0.85, 5)
    weighted_linear_fit_model = WeightedLinearRegressionModel(yearly_amount_input, NUMBER_OF_STOCK_DAYS_IN_YEAR, NUMBER_OF_STOCK_DAYS_IN_YEAR)
    future_limit_model = FutureLimitModel(yearly_amount_input, 0.997, 10)
    averaged_future_limit_model = AveragedFutureLimitModel(yearly_amount_input, 0.997, 10, NUMBER_OF_STOCK_DAYS_IN_YEAR)
    
    simulator.simulate(constant_dollar_random_model)
    simulator.plot(log_color_plot=False)
    print(f'Constant dollar:\n{simulator.metrics()}')

    simulator.reset(simulation_parameters)
    simulator.simulate(lump_sum_model)
    simulator.plot(log_color_plot=False)
    print(f'Lump sum:\n{simulator.metrics()}')

    # simulator.reset(simulation_parameters)
    # simulator.simulate(linear_distribution_model)
    # simulator.plot(log_color_plot=False)
    # print(f'Linear distribution:\n{simulator.metrics()}')

    simulator.reset(simulation_parameters)
    simulator.simulate(lump_linear_distribution_model)
    simulator.plot(log_color_plot=False)
    print(f'Lump Linear distribution:\n{simulator.metrics()}')
    
    # simulator.reset(simulation_parameters)
    # simulator.simulate(linear_fit_model)
    # simulator.plot(log_color_plot=False)
    # print(f'Linear regression:\n{simulator.metrics()}')
    
    # simulator.reset(simulation_parameters)
    # simulator.simulate(weighted_linear_fit_model)
    # simulator.plot(log_color_plot=False)
    # print(f'Weighted linear regression:\n{simulator.metrics()}')

    simulator.reset(simulation_parameters)
    simulator.simulate(future_limit_model)
    simulator.plot(log_color_plot=False)
    print(f'Future limit model:\n{simulator.metrics()}')

    # simulator.reset(simulation_parameters)
    # simulator.simulate(averaged_future_limit_model)
    # simulator.plot(log_color_plot=False)
    # print(f'Averaged Future limit model:\n{simulator.metrics()}')

    plt.show()
    input()
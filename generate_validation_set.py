import os
import random
from datetime import datetime
import pytz

from utils import get_data_for_stock
from simulation import SimulationParameters

from tqdm import tqdm
import pandas as pd

file_name = 'validation_set.csv'

min_number_days = 365 * 5
max_number_days = 365 * 30
buffer_number_days_for_model = 365 * 2
number_runs_per_stock = 250
validation_stocks = ['VTI', 'VNQ', 'VDE', 'RYE', 'QCLN', 'VIG', 'VGT', 'SPY', 'VYM', 'SCHD', 'VDC', 'VUG', 'VONE', 'VTHR', 'VDE', 'VOO', 'VHT', 'VWO', 'VOX', 'VIS', 'VOT', 'VOE', 'VTWG', 'VTWV', 'VTWO', 'IVOG', 'VIOV', 'MGK', 'MGV', '^IXIC', '^DJI', '^RUT', '^FTSE', '^NYA', '^XAX', '^BUK100P', '^RUT', '^VIX', '^GDAXI', '^FCHI', '^NZ50', '^BVSP', '^AORD', 'AAPL', 'TSLA', 'GOOGL', 'MSFT', 'NVDA', 'AMZN', 'META', 'GOOG', 'COST', 'JPM', 'XOM', 'JNJ']

if __name__ == '__main__':
    validation_path = 'validation_sets/'
    file_path = validation_path + file_name
    
    if os.path.exists(file_path):
        print('Validation file already exists. Either delete it or rename the validation file.')
        exit(1)
    
    today_datetime = datetime.now().astimezone(pytz.timezone('US/Eastern'))
    
    # Check all tickers work.
    for stock in validation_stocks:
        data = get_data_for_stock(stock, today_datetime)
        assert data.shape[0] - buffer_number_days_for_model > min_number_days, f'Not enough data for validation on {stock}.'
    df = pd.DataFrame()
    for stock in tqdm(validation_stocks):
        data = get_data_for_stock(stock, today_datetime)
        for ii in tqdm(range(number_runs_per_stock), desc=f'{stock}'):
            random_seed = random.randint(0, 10000000000)
            start_day = random.randint(buffer_number_days_for_model, data.shape[0] - min_number_days - 1)
            end_day = random.randint(start_day + min_number_days, min(start_day + max_number_days, data.shape[0] - 1))
            start_date = data.index[start_day].date()
            end_date = data.index[end_day].date()
            yearly_amount_input = random.uniform(5000, 30000)
            starting_account_balance = 0

            # Can buy roughly 2 a year.
            if data['Open'].iloc[-1] < yearly_amount_input / 2:
                fractional_shares = random.random() < 0.5
            else:
                fractional_shares = True
            investment_input_cycle_days = random.randint(7, 28)
            start_day_of_cycle = random.randint(0, investment_input_cycle_days - 1)
                
            simulation_parameters = SimulationParameters()
            simulation_parameters.parse_from_inputs(stock, random_seed, start_date, end_date, start_day_of_cycle, yearly_amount_input, starting_account_balance, fractional_shares, investment_input_cycle_days)
            df = pd.concat([df, pd.DataFrame([simulation_parameters.convert_to_dict()])], ignore_index=True)
    df.to_csv(file_path, index=False)

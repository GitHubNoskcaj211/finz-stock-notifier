import os
import json
from tqdm import tqdm
from datetime import datetime
import pytz
import pandas as pd
from matplotlib import pyplot as plt

from simulation import Simulator, SimulationParameters, EXAMPLE_STAT_KEY
from utils import get_data_for_stock
from model import BaseModel, ConstantDollarRandomModel, LumpSumModel, LinearRegressionModel, WeightedLinearRegressionModel,LinearDistributionModel, LumpLinearDistributionModel, FutureLimitModel, NUMBER_OF_STOCK_DAYS_IN_YEAR

VALIDATION_PATH = 'validation_sets/'
RESULT_PATH = 'validation_results/'
SAVE_BUFFER = 400

class Validation():
    def __init__(self, model_list: list, input_file_path, result_file_path):
        for model in model_list:
            if not isinstance(model, BaseModel):
                raise Exception('Model in model_list given to Validation object is not a BaseModel instance.')
        self.model_list = model_list
        self.input_file_path = input_file_path
        self.result_file_path = result_file_path
        self.downloaded_data = {}

        if os.path.exists(result_file_path):
            self.df = pd.read_csv(result_file_path)
        else:
            self.df = pd.read_csv(input_file_path)

        model_names = [model.name for model in self.model_list]
        assert len(model_names) == len(set(model_names)), 'Duplicate model names. Results will be overwritten.'
    
    def run_instance_with_model(self, simulation_parameters: SimulationParameters, model: BaseModel):
        if simulation_parameters.stock not in self.downloaded_data:
            today_datetime = datetime.now().astimezone(pytz.timezone('US/Eastern'))
            self.downloaded_data[simulation_parameters.stock] = get_data_for_stock(simulation_parameters.stock, today_datetime)
        simulator = Simulator(simulation_parameters, data=self.downloaded_data[simulation_parameters.stock])
        model.annual_money_input = simulation_parameters.yearly_amount_input
        simulator.simulate(model)
        return simulator.metrics()
    
    def run(self):
        save_counter = 0
        for ii in tqdm(range(self.df.shape[0]), desc='Simulation Instance'):
            eval_dictionary = self.df.iloc[ii]
            simulation_parameters = SimulationParameters()
            simulation_parameters.parse_from_dict(eval_dictionary)
            for model in self.model_list:
                if f'{model.name}_{EXAMPLE_STAT_KEY}' in eval_dictionary.keys() and not pd.isna(eval_dictionary[f'{model.name}_{EXAMPLE_STAT_KEY}']):
                    continue

                stats = validation.run_instance_with_model(simulation_parameters, model)
                stats = {f'{model.name}_{stat}': value for stat, value in stats.items()}
                self.df.loc[ii, stats.keys()] = pd.Series(stats)

                save_counter += 1
                if save_counter >= SAVE_BUFFER:
                    self.df.to_csv(self.result_file_path, index=False)
                    save_counter = 0
        self.df.to_csv(self.result_file_path, index=False)
            

if __name__ == '__main__':
    file_name = 'validation_set.csv'
    
    input_file_path = VALIDATION_PATH + file_name
    result_file_path = RESULT_PATH + file_name
    
    yearly_amount_input = 0
    constant_dollar_random_model = ConstantDollarRandomModel(yearly_amount_input, NUMBER_OF_STOCK_DAYS_IN_YEAR)
    lump_sum_model = LumpSumModel(yearly_amount_input)
    lump_linear_distribution_model = LumpLinearDistributionModel(yearly_amount_input, 0.85, 5)
    future_limit_model = FutureLimitModel(yearly_amount_input, 0.997, 10)
    validation = Validation([constant_dollar_random_model, lump_sum_model, lump_linear_distribution_model, future_limit_model], input_file_path, result_file_path)
    validation.run()
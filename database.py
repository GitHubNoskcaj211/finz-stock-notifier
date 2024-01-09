import gspread
from oauth2client.service_account import ServiceAccountCredentials
from utils import InternalLogicException, UserInputException, try_cast, ticker_exists, get_data_for_stock, get_today
from model import LumpSumModel, NUMBER_OF_STOCK_DAYS_IN_YEAR
from enum import Enum
from datetime import datetime, timedelta
import math
import pandas as pd

database_spreadsheet_id = '19IjGW4jdqqzrNAO7mFsO5e43WcwMTL4nIGvUqlcwp4A'
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
LAST_DATE_SUCCESS_COLUMN = 4
NUM_CURRENT_DAY_FAILURES_COLUMN = 5
ORDER_FULFILLMENT_WAIT_TIME_DAYS = 10

class InvestmentInputSchedules(Enum):
    MONDAYS = 1
    TUESDAYS = 2
    WEDNESDAYS = 3
    THURSDAYS = 4
    FRIDAYS = 5

investment_input_schedules_spreadsheet_to_enum = {
    'Weekly on Mondays': InvestmentInputSchedules.MONDAYS,
    'Weekly on Tuesdays': InvestmentInputSchedules.TUESDAYS,
    'Weekly on Wednesdays': InvestmentInputSchedules.WEDNESDAYS,
    'Weekly on Thursdays': InvestmentInputSchedules.THURSDAYS,
    'Weekly on Fridays': InvestmentInputSchedules.FRIDAYS,
}

class Database:
    def __init__(self):
        self.google_credentials = ServiceAccountCredentials.from_json_keyfile_name("spreadsheet_creds.json", SCOPE)
        self.spreadsheet_client = gspread.authorize(self.google_credentials)
        try:
            self.database_sheet = self.spreadsheet_client.open_by_key(database_spreadsheet_id).worksheet('Database')
        except gspread.exceptions.WorksheetNotFound:
            raise InternalLogicException
        
        self.users = []
        database_data = self.database_sheet.get_all_records()

        for ii, user_row in enumerate(database_data):
            database_row_index = ii + 2
            user = User(self.database_sheet, database_row_index, user_row)
            try:
                user.populate_user_data()
            except Exception:
                if user.user_error_message == '':
                    user.user_error_message = 'Error loading user values from spreadsheet: Something went wrong with no known cause.'
            self.users.append(user)

class User:
    def __init__(self, database_sheet, database_row_index, user_row):
        self.google_credentials = ServiceAccountCredentials.from_json_keyfile_name("spreadsheet_creds.json", SCOPE)
        self.spreadsheet_client = gspread.authorize(self.google_credentials)

        self.database_sheet = database_sheet
        self.database_row_index = database_row_index
        self.loaded = False
        self.user_error_message = ''
        try:
            self.email = try_cast(user_row['Email'], str)
            self.spreadsheet_id = try_cast(user_row['Spreadsheet ID'], str)
            self.subscribed = user_row['Subscribed?'] == 'Yes'
            self.last_date_success = try_cast(user_row['Last Date Success'], str)
            self.num_current_day_failures = try_cast(user_row['Num Current Day Failures'], int)
        except Exception:
            raise InternalLogicException
        
    def get_daily_investment_amount(self, date):
        total = 0
        if date.weekday() == 0:
            total += self.investment_schedule_data.loc[self.investment_schedule_data['Investment Frequency'] == InvestmentInputSchedules.MONDAYS, 'Amount'].sum()
        if date.weekday() == 1:
            total += self.investment_schedule_data.loc[self.investment_schedule_data['Investment Frequency'] == InvestmentInputSchedules.TUESDAYS, 'Amount'].sum()
        if date.weekday() == 2:
            total += self.investment_schedule_data.loc[self.investment_schedule_data['Investment Frequency'] == InvestmentInputSchedules.WEDNESDAYS, 'Amount'].sum()
        if date.weekday() == 3:
            total += self.investment_schedule_data.loc[self.investment_schedule_data['Investment Frequency'] == InvestmentInputSchedules.THURSDAYS, 'Amount'].sum()
        if date.weekday() == 4:
            total += self.investment_schedule_data.loc[self.investment_schedule_data['Investment Frequency'] == InvestmentInputSchedules.FRIDAYS, 'Amount'].sum()
        return total

    def input_money_to_stock_balances(self, date):
        daily_investment_amount = self.get_daily_investment_amount(date)

        for index, row in self.stock_data.iterrows():
            self.stock_data.loc[index, 'Current Balance'] += daily_investment_amount * row['Percentage to Input']

    def check_and_update_newly_fulfilled_orders(self):
        message_for_unfulfilled_orders = ''

        today_datetime, today_date = get_today()
        for index, row in self.orders_data.iterrows():
            if row['Fulfilled?'] == 'Yes':
                continue
            if row['Stock'] == '':
                continue

            stock = row['Stock']
            data = get_data_for_stock(stock, today_datetime)
            data_in_fulfillment_window = data[(row['Date'] + timedelta(days=1)):]
            if (data_in_fulfillment_window['Low'] < row['Limit Price']).any():
                self.orders_data.loc[index, 'Fulfilled?'] = 'Yes'
            elif len(data_in_fulfillment_window.index) >= ORDER_FULFILLMENT_WAIT_TIME_DAYS:
                message_for_unfulfilled_orders += f'''<br>Buy order for date {str(row["Date"])} and stock {stock} may have been unfulfilled (as 10 consecutive open prices were higher than the limit price of the order).
                <br>If this order was fulfilled, please change the "Fulfilled?" column in the "Orders" sheet to "Yes".
                <br>If the order was not fulfilled, please cancel that order, delete the corresponding row from the "Orders" sheet, and add {row["Amount"] * row["Limit Price"]} to the "Current Balance" for the associated stock on the "Stocks" sheet.
                <br>Double check that the sum of your available cash in your account (total cash minus any cash withheld for limit orders) is equal to the the sum of all balances in the "Stocks" sheet.
                If it is not, change the balances (however you like because values drift over time) such that these values match.<br><br>'''

        return message_for_unfulfilled_orders

    def update_user_sheets(self):
        self.user_stock_sheet.update(range_name='A1:C', values=[self.stock_data.columns.values.tolist()] + self.stock_data.values.tolist())
        transformed_orders_data = self.orders_data
        transformed_orders_data['Date'] = transformed_orders_data['Date'].apply(lambda date: str(date))
        self.orders_sheet.update(range_name='A1:E', values=[transformed_orders_data.columns.values.tolist()] + transformed_orders_data.values.tolist())
    
    def get_model_for_stock(self, stock):
        current_balance_list = self.stock_data.loc[self.stock_data['Stock'] == stock, 'Current Balance'].tolist()
        if len(current_balance_list) == 0:
            return None
        model = LumpSumModel(current_balance_list[0])
        return model

    def notify_buy_orders(self):
        message = ''
        figures = []
        success = True

        today_datetime, today_date = get_today()

        for index, row in self.stock_data.iterrows():
            stock = row['Stock']
            balance = row['Current Balance']
            model = self.get_model_for_stock(stock)
            data = get_data_for_stock(stock, today_datetime)
            open_price = round(data['Open'].iloc[-1], 2)
            stock_today = data.index[-1].date()
            if stock_today != today_date:
                message += f'Warning: stock date and python date not matching for {stock}. Data might be stale.<br>'
            try:
                buy_rate = model.analyze_stock(data)
            except Exception as e:
                print(f'Modeling Error: {str(e)}')
                message += f'{stock} had a modeling error.<br>'
                success = False
                continue
            
            if buy_rate * open_price > balance:
                buy_rate = balance / open_price if open_price > 0 else 0

            num_to_buy = math.floor(buy_rate)
            
            message += f'{stock}: Limit buy order {num_to_buy} share(s) at price {open_price}.<br>'
            figures.append(model.get_market_figure(data['Open'].iloc[-NUMBER_OF_STOCK_DAYS_IN_YEAR:], stock)[0])
            
            self.stock_data.loc[index, 'Current Balance'] -= open_price * num_to_buy
            if num_to_buy > 0:
                order = pd.DataFrame([{'Date': today_date, 'Stock': stock, 'Amount': num_to_buy, 'Limit Price': open_price, 'Fulfilled?': 'No'}])
                if self.orders_data.empty:
                    self.orders_data = pd.concat([order], ignore_index=True)
                else:
                    self.orders_data = pd.concat([self.orders_data, order], ignore_index=True)
        return message, figures, success

    def populate_user_data(self):
        self.stock_data = pd.DataFrame()
        self.investment_schedule_data = pd.DataFrame()
        self.orders_data = pd.DataFrame()
        self.user_error_message = ''

        try:
            self.user_stock_sheet = self.spreadsheet_client.open_by_key(self.spreadsheet_id).worksheet('Stocks')
            self.investment_schedule_sheet = self.spreadsheet_client.open_by_key(self.spreadsheet_id).worksheet('Investment Schedule')
            self.orders_sheet = self.spreadsheet_client.open_by_key(self.spreadsheet_id).worksheet('Orders')
        except Exception:
            self.user_error_message += 'Error loading user values from spreadsheet: Could not find "Stocks", "Investment Schedule", or "Orders" worksheet (these might need to be renamed).<br>'
            raise UserInputException
        
        try:
            user_stock_sheet_values = self.user_stock_sheet.get_all_values()
            investment_schedule_sheet_values = self.investment_schedule_sheet.get_all_values()
            orders_sheet_values = self.orders_sheet.get_all_values()
            self.stock_data = pd.DataFrame(user_stock_sheet_values[1:], columns=user_stock_sheet_values[0])
            self.investment_schedule_data = pd.DataFrame(investment_schedule_sheet_values[1:], columns=investment_schedule_sheet_values[0])
            self.orders_data = pd.DataFrame(orders_sheet_values[1:], columns=orders_sheet_values[0])
        except Exception:
            self.user_error_message += 'Error loading user values from spreadsheet: Could not get data from either stock, investment schedule, or orders sheet. Ensure that the header row still exists.<br>'
            raise UserInputException

        if 'Stock' not in self.stock_data or 'Current Balance' not in self.stock_data or 'Percentage to Input' not in self.stock_data:
            self.user_error_message += f'Error loading user values from spreadsheet: Could not find column name "Stock", "Current Balance", or "Percentage to Input".<br>'
            raise UserInputException
        
        try:
            self.stock_data['Stock'] = self.stock_data['Stock'].apply(lambda stock: try_cast(stock, str))
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: "Stock" value is not a valid string.<br>'
            raise UserInputException

        self.stock_data = self.stock_data[self.stock_data['Stock'] != '']
        
        if not self.stock_data['Current Balance'].str.startswith('$').all():
            self.user_error_message += f'Error loading user values from spreadsheet: Some "Current Balance" does not start with a "$".<br>'
            raise UserInputException
        if not self.stock_data['Percentage to Input'].str.endswith('%').all():
            self.user_error_message += f'Error loading user values from spreadsheet: Some "Percentage to Input" does not end with a "%".<br>'
            raise UserInputException
        
        try:
            self.stock_data['Current Balance'] = self.stock_data['Current Balance'].apply(lambda balance: try_cast(balance[1:].replace(',', ''), float))
            self.stock_data['Percentage to Input'] = self.stock_data['Percentage to Input'].apply(lambda percentage_to_input: try_cast(percentage_to_input[:-1], float) / 100)
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: "Balance" or "Percentage to Input" is not a valid for some rows.<br>'
            raise UserInputException
                
        if (self.stock_data['Current Balance'] < 0).any():
            self.user_error_message += f'Error loading user values from spreadsheet: Balance less than 0 for some stock.<br>'
            raise UserInputException
        if (self.stock_data['Percentage to Input'] < 0).any():
            self.user_error_message += f'Error loading user values from spreadsheet: Investment input percentage less than 0 for some stock.<br>'
            raise UserInputException
        bad_tickers = self.stock_data.loc[~self.stock_data['Stock'].apply(ticker_exists), 'Stock'].tolist()
        if len(bad_tickers) > 0:
            self.user_error_message += f'Error loading user values from spreadsheet: {bad_tickers} is/are not a valid ticker.<br>'
            raise UserInputException
            
        if self.stock_data['Stock'].duplicated().any():
            self.user_error_message += f'Error loading user values from spreadsheet: Some tickers appears multiple times in the "Stock" sheet. This will lead to undefined behavior.<br>'
            raise UserInputException
        
        if 'Investment Frequency' not in self.investment_schedule_data or 'Amount' not in self.investment_schedule_data:
            self.user_error_message += f'Error loading user values from spreadsheet: Could not find column name "Investment Frequency" or "Amount".<br>'
            raise UserInputException
        
        try:
            self.investment_schedule_data['Investment Frequency'] = self.investment_schedule_data['Investment Frequency'].apply(lambda investment_frequency: try_cast(investment_frequency, str))
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: "Investment Frequency" is not a valid string.<br>'
            raise UserInputException
        
        self.investment_schedule_data = self.investment_schedule_data[self.investment_schedule_data['Investment Frequency'] != '']
        
        if self.investment_schedule_data['Investment Frequency'].duplicated().any():
            self.user_error_message += f'Error loading user values from spreadsheet: Some investment frequencies appears multiple times in the "Investment Schedule" sheet.<br>'
            raise UserInputException
        
        if not self.investment_schedule_data['Amount'].str.startswith('$').all():
            self.user_error_message += f'Error loading user values from spreadsheet: Some "Amount" does not start with a "$".<br>'
            raise UserInputException
        
        try:
            self.investment_schedule_data['Amount'] = self.investment_schedule_data['Amount'].apply(lambda amount: try_cast(amount[1:].replace(',', ''), float))
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: "Amount" is not a valid for some rows.<br>'
            raise UserInputException

        if (self.investment_schedule_data['Amount'] < 0).any():
            self.user_error_message += f'Error loading user values from spreadsheet: Amount less than 0 for some stock.<br>'
            raise UserInputException
        
        try:
            self.investment_schedule_data['Investment Frequency'] = self.investment_schedule_data['Investment Frequency'].apply(lambda investment_frequency: investment_input_schedules_spreadsheet_to_enum[investment_frequency])
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: Some "Investment Frequency" is valid from possibilities ({", ".join(investment_input_schedules_spreadsheet_to_enum.keys())}).<br>'
            raise UserInputException

        try:
            assert abs(self.stock_data['Percentage to Input'].sum() - 1) < 1e-3
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: Sum of investment input percentages does not equal 100%.<br>'
            raise UserInputException
        
        if 'Date' not in self.orders_data or 'Stock' not in self.orders_data or 'Amount' not in self.orders_data or 'Limit Price' not in self.orders_data or 'Fulfilled?' not in self.orders_data:
            self.user_error_message += f'Error loading user values from spreadsheet: Could not find column name "Date", "Stock", "Amount", "Limit Price", or "Fulfilled?".<br>'
            raise UserInputException
        
        try:
            self.orders_data['Date'] = self.orders_data['Date'].apply(lambda date_string: datetime.strptime(date_string, '%Y-%m-%d').date())
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: "Date" is not a valid for some rows. Ensure format is "YYYY-MM-DD".<br>'
            raise UserInputException
        
        if not self.orders_data['Limit Price'].str.startswith('$').all():
            self.user_error_message += f'Error loading user values from spreadsheet: Some "Limit Price" does not start with a "$".<br>'
            raise UserInputException
        
        try:
            self.orders_data['Amount'] = self.orders_data['Amount'].apply(lambda amount: try_cast(amount, float))
            self.orders_data['Limit Price'] = self.orders_data['Limit Price'].apply(lambda limit_price: try_cast(limit_price[1:].replace(',', ''), float))
        except Exception:
            self.user_error_message += f'Error loading user values from spreadsheet: "Amount" or "Limit Price" is not a valid for some rows.<br>'
            raise UserInputException

        self.loaded = True

    def set_last_date_success(self, date):
        try:
            self.database_sheet.update_cell(self.database_row_index, LAST_DATE_SUCCESS_COLUMN, str(date))
            self.last_date_success = str(date)
        except gspread.exceptions.APIError:
            raise InternalLogicException

    def set_num_current_day_fails(self, num_fails):
        try:
            self.database_sheet.update_cell(self.database_row_index, NUM_CURRENT_DAY_FAILURES_COLUMN, num_fails)
            self.num_current_day_failures = num_fails
        except gspread.exceptions.APIError:
            raise InternalLogicException

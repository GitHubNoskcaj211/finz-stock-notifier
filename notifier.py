from utils import get_data_for_stock, send_email, send_fail_email, EmailContent, get_today
from database import Database

# TODO Switch prints to log messages
# TODO New class that downloads and caches stock data

MAX_NUM_FAILS = 5

def run(user, should_email = False, should_print = False, send_figures = False) -> bool:
    success = True
    if not user.subscribed:
        return success
    
    today_datetime, today_date = get_today()

    subject = f'Finz Stock Notification for {today_date}\n'
    message = ''
    figures = []

    if user.last_date_success == str(today_date):
        return success
    
    if user.loaded:
        user.input_money_to_stock_balances(today_date)
        try:
            message, figures, success = user.notify_buy_orders()
        except Exception:
            message, figures, success = 'Unknown error occured in modeling buy orders.<br>', [], False
        if success:
            try:
                message += user.check_and_update_newly_fulfilled_orders()
            except Exception:
                message, figures, success = 'Unknown error occured in updating fulfilled orders.<br>', [], False
        if success:
            try:
                user.update_user_sheets()
            except Exception:
                send_fail_email(f'{user.email} failed while updating user values (check that the user sheet is not malformed).')
    else:
        success = False
        message += user.user_error_message

    if not success and user.num_current_day_failures >= MAX_NUM_FAILS:
        send_fail_email(f'{user.email} reached max num fails.')
        success = True

    if should_print:
        print_message = message.replace('<br>', '\n')
        print(f'Message for user {user.email}:\n{print_message}')
    if success and should_email:
        send_email(EmailContent(subject, message, figures, [user.email]))

    if success:
        user.set_last_date_success(today_date)
        user.set_num_current_day_fails(0)
    else:
        user.set_num_current_day_fails(user.num_current_day_failures + 1)

    return success

def main(data, context):
    should_email = True
    should_print = True
    send_figures = True

    try:
        database = Database()
        users = database.users
    except Exception as e:
        print(f'Database error: {str(e)}')
        send_fail_email(f'Database error: {str(e)}')
        users = []
    
    all_success = True
    for user in users:
        success = run(user, should_email = should_email, should_print = should_print, send_figures = send_figures)
        all_success = success and all_success
        print(f'{user.email} Success? : {success}')

    print(f'All Success: {all_success}')
    if not all_success:
        raise Exception('Something unsuccessful. Need to retry.')
    
if __name__ == '__main__':
    main('Fake data.', 'Fake context')
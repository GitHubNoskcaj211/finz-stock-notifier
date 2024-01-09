import yfinance as yf
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import io
from datetime import datetime, timedelta
import pytz

from hidden import from_email, from_password, fail_email_address

class EmailContent:
    def __init__(self, subject, message, figures, to_list):
        self.subject = subject
        self.message = message
        self.figures = figures
        self.to_list = to_list

def try_cast(obj, cast):
    try:
        return cast(obj)
    except Exception:
        raise InternalLogicException

def average(lst):
    return 0 if len(lst) == 0 else sum(lst) / len(lst)

def get_data_for_stock(stock, end_date):
    return yf.download(stock, end=end_date + timedelta(days=1), progress=False)

def get_today():
    today_datetime = datetime.now().astimezone(pytz.timezone('US/Eastern'))
    today_date = today_datetime.date()
    return today_datetime, today_date

def send_fail_email(reason):
    send_email(EmailContent('Stock Notifier Failed', f'Please check stock notifier for {reason}.', [], [fail_email_address]))

def send_email(email_content):
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(from_email, from_password)
    
    subject = email_content.subject
    message = email_content.message
    figures = email_content.figures
    to_list = email_content.to_list

    email_msg = MIMEMultipart()
    email_msg['From'] = from_email
    email_msg['Subject'] = subject
    email_msg.attach(MIMEText(message, "html"))
    for figure in figures:
        figure_file = io.BytesIO()
        figure.savefig(figure_file, format='png')
        figure_file.seek(0)
        img = MIMEImage(figure_file.read())
        img.add_header("Content-ID", "<{}>".format(figure.axes[0].get_title()))
        email_msg.attach(img)
    for recipient in to_list:
        email_msg['To'] = recipient
        server.sendmail(from_email, recipient, email_msg.as_string())
    server.quit()

def ticker_exists(ticker_string: str) -> bool:
    info = yf.Ticker(ticker_string).history(
        period='14d',
        interval='1d')
    return len(info) > 0
        

class InternalLogicException(Exception):
    'Thrown when something wrong happens in the script. This will be caught and handled to fail gracefully.'
    pass

class UserInputException(Exception):
    'Thrown when there is an error on the user interface with a value they input.'
    pass

const requests_spreadsheets_id = "19IjGW4jdqqzrNAO7mFsO5e43WcwMTL4nIGvUqlcwp4A";
const sign_up_action = "Sign Up";
const unsubscribe_action = "Unsubscribe";
const template_stock_spreadsheet_id = "1SVu3OMEN9P48hH1GWdBoW8ALdGqRF6SrSvddBAZwEaM";
const subscribed_value = "Yes";
const spreadsheet_service_account = 'spreadsheets@stock-notifier-373901.iam.gserviceaccount.com';

function send_email(to_email, message) {
  var subject = 'Message from Finz';
  GmailApp.sendEmail(to_email, subject, message);
}

function get_database_row_index_if_email_exists(database, email) {
  for (let ii = 1; ii < database.length; ii++) {
    let row = database[ii];
    if (row[0] === email) {
      return ii;
    }
  }
  return null;
}

function create_new_user_spreadsheet(email) {
  const new_spreadsheet = DriveApp.getFileById(template_stock_spreadsheet_id).makeCopy(`${email} Stocks`);  
  return new_spreadsheet.getId();
}

function get_default_last_date_success() {
  return "2020-01-01";
}

function get_default_num_current_day_failures() {
  return 0;
}

function create_new_user(database_sheet, email) {
  const user_spreadsheet_id = create_new_user_spreadsheet(email);
  
  
  const user_spreadsheet_file = DriveApp.getFileById(user_spreadsheet_id);
  user_spreadsheet_file.setShareableByEditors(false)
  user_spreadsheet_file.addEditor(email);
  user_spreadsheet_file.addEditor(spreadsheet_service_account);

  const user_values = [email, user_spreadsheet_id, subscribed_value, get_default_last_date_success(), get_default_num_current_day_failures()];
  database_sheet.appendRow(user_values);
  
  return database_sheet.getLastRow() - 1;
}

function unsubscribe_user(database_sheet, user_row_index) {
  database_sheet.getRange(user_row_index + 1, 3).setValue("No");
}

function resubscribe_user(database_sheet, user_row_index) {
  database_sheet.getRange(user_row_index + 1, 3).setValue("Yes");
}

function process_request(database_sheet, email, action) {
  const database = database_sheet.getDataRange().getValues();
  let row_index_if_exists = get_database_row_index_if_email_exists(database, email);
  if (row_index_if_exists === null && action === sign_up_action) {
    row_index_if_exists = create_new_user(database_sheet, email);
    send_email(email, `You have been successfully added to Finz - use your shared spreadsheet (named "${email} Stocks" at link ${DriveApp.getFileById(database_sheet.getRange(row_index_if_exists + 1, 2).getValue()).getUrl()}) to choose your stocks and preferences.`);
  } else if (row_index_if_exists !== null && action === unsubscribe_action) {
    unsubscribe_user(database_sheet, row_index_if_exists);
    send_email(email, "You have been successfully unsubscribed from Finz.");
  } else if (row_index_if_exists !== null && action === sign_up_action) {
    resubscribe_user(database_sheet, row_index_if_exists);
    send_email(email, `You have been successfully resubscribed from Finz. You can use the spreadsheet you were using before (named "${email} Stocks" at link ${DriveApp.getFileById(database_sheet.getRange(row_index_if_exists + 1, 2).getValue()).getUrl()}).`);
  }
}

function process_requests() {
  const spreadsheet = SpreadsheetApp.openById(requests_spreadsheets_id);
  
  const requests_sheet = spreadsheet.getSheetByName("Requests");
  const database_sheet = spreadsheet.getSheetByName("Database");
  
  const requests = requests_sheet.getDataRange().getValues();
  
  let any_error = null;
  for (let ii = 1; ii < requests.length; ii++) {
    let row = requests[ii];
    let [timestamp, email, action, processed] = row;
    if (timestamp !== "" && processed === "") {
      try {
        process_request(database_sheet, email, action);
        requests_sheet.getRange(ii + 1, 4).setValue("Yes");
      } catch (error) {
        console.log(error);
        requests_sheet.getRange(ii + 1, 4).setValue("Yes");
        any_error = error;
      }
    }
  }
  
  if (any_error !== null) {
    throw any_error;
  }
}

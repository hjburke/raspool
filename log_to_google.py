import time
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import config

GDOCS_SPREADSHEET_NAME = 'raspool-log'
GDOCS_TEMPS_WORKSHEET_NAME = 'Temperatures'

def login_open_sheet(oauth_key_file, spreadsheet):
    """Connect to Google Docs spreadsheet and return the first worksheet."""
    try:
        scope =  ['https://spreadsheets.google.com/feeds']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(oauth_key_file, scope)
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open(spreadsheet)
        return spreadsheet
    except Exception as ex:
        logging.error('Unable to login and get spreadsheet.  Check OAuth credentials, spreadsheet name, and make sure spreadsheet is shared to the client_email address in the OAuth .json file!')
        logging.error('Google sheet login failed with error: %s' % ex)

def log_temps_to_google(logtime,pump,solar,air_temp,pool_temp,solar_temp,lux,notes):

    sht = login_open_sheet(config.GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME)

    #
    # Try to open the worksheet, if it fails then create it
    #
    try:
        wks = sht.worksheet(GDOCS_TEMPS_WORKSHEET_NAME)
    except:
        logging.info('Worksheet %s does not exist, creating' % GDOCS_TEMPS_WORKSHEET_NAME)
        wks = sht.add_worksheet(title=GDOCS_TEMPS_WORKSHEET_NAME, rows="1", cols="8")

        wks.update_cell(1,1,"Date")
        wks.update_cell(1,2,"Pump Status")
        wks.update_cell(1,3,"Solar Status")
        wks.update_cell(1,4,"Air Temp")
        wks.update_cell(1,5,"Pool Temp")
        wks.update_cell(1,6,"Solar Temp")
        wks.update_cell(1,7,"Lux")
        wks.update_cell(1,8,"Notes")

    #
    # Add a row with the data
    #
    try:
        wks.append_row((logtime,pump,solar,air_temp,pool_temp,solar_temp,lux,notes))
    except:
        logging.warning('Error appending a row to the feeding worksheet')

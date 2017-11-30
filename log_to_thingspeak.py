"""log_to_thingspeak.py

This module provides data logging to Thingspeak.

"""

import time
import json
import requests
import config

base_url = 'https://api.thingspeak.com/update.json?api_key='+config.ts_api_key

def update_temps(air_temp,pool_temp,solar_temp,lux,pump_status,solar_status):
	payload = {
		"field1": "{0:5.1f}".format(pool_temp),
		"field2": "{0:5.1f}".format(solar_temp),
		"field3": "{0:5.1f}".format(air_temp),
		"field4": lux,
		"field5": pump_status,
		"field6": solar_status
	}

	try:
		response = requests.post(base_url, data=json.dumps(payload), headers={'content-type':'application/json'})
	except:
		return 500

	return response.status_code

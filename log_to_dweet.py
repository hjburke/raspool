"""log_to_dweet.py

This module provides data logging to dweet.io.

If you are using the unlocked (free) things, then set the dweet_id in config.py to obfuscate your
thing name.
If you are using locked things, then set the dweet_key in config.py.

"""

import time
import json
import requests
import config

base_url = 'https://dweet.io/dweet/for/'
thing_name_temp = 'raspool-temp'
thing_name_equipment = 'raspool-equip'

if (config.dweet_id != ""):
	thing_name_temp += '-'+config.dweet_id
	thing_name_equipment += '-'+config.dweet_id

if (config.dweet_key != ""):
	thing_name_temp += '?key='+config.dweet_key
	thing_name_equipment += '?key='+config.dweet_key

def dweet_update_temps(air_temp,pool_temp,solar_temp,lux):
	payload = {
		"logtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())),
		"air_temp": "{0:5.1f}".format(air_temp),
		"pool_temp": "{0:5.1f}".format(pool_temp),
		"solar_temp": "{0:5.1f}".format(solar_temp),
		"lux": lux
	}

	try:
		response = requests.post(base_url+thing_name_temp, data=json.dumps(payload), headers={'content-type':'application/json'})
	except:
		return 500

	return response.status_code

def dweet_update_equipment(pump_status,solar_status):
	payload = {
		"logtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())),
		"pump_status":pump_status,
		"solar_status":solar_status
	}

	try:
		response = requests.post(base_url+thing_name_equipment, data=json.dumps(payload), headers={'content-type':'application/json'})
	except:
		return 500

	return response.status_code

"""log_to_mqtt.py

This module provides data logging to an MQTT message broker.

"""

import paho.mqtt.publish as publish
import time
import json
import config

def mqtt_update_temps(air_temp,pool_temp,solar_temp,lux):
	payload = {
		"logtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())),
		"air_temp": "{0:5.1f}".format(air_temp),
		"pool_temp": "{0:5.1f}".format(pool_temp),
		"solar_temp": "{0:5.1f}".format(solar_temp),
		"lux": lux
	}

	try:
		publish.single("tele/raspool/SENSOR", json.dumps(payload), hostname=config.mqtt_host, auth = {'username':config.mqtt_user, 'password':config.mqtt_pass})
	except:
		return 500

	return 200

def mqtt_update_equipment(pump_status,solar_status):
	payload = {
		"logtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())),
		"pump_status":pump_status,
		"solar_status":solar_status
	}

	try:
		publish.single("tele/raspool/STATE", json.dumps(payload), hostname=config.mqtt_host, auth = {'username':config.mqtt_user, 'password':config.mqtt_pass})
	except:
		return 500

	return 200

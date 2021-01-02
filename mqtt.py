"""mqtt.py

This module provides data logging and commands to/from an MQTT message broker.

"""

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import time
import json
import config
import logging

def on_connect(client, userdata, flags, rc):
    logging.info("Connected to MQTT Server RC="+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(config.mqtt_base_topic+"#")
    # Add callbacks for the specific commands
    for cb in userdata:
        client.message_callback_add(config.mqtt_base_topic+cb[0], cb[1])

def on_disconnect(client, userdata, flags, rc):
    logging.info("Disconnected to MQTT Server RC="+str(rc))

def init(callbacks):
    global mc
    mc = mqtt.Client(client_id=config.mqtt_client, userdata=callbacks)
    mc.username_pw_set(config.mqtt_user,config.mqtt_pass)
    mc.on_connect = on_connect
    mc.on_disconnect = on_disconnect
    mc.connect(config.mqtt_host)
    return mc

def publish_status(AirTemp, PoolTemp, SolarTemp, ReturnTemp, Lux, PumpStatus, SolarStatus, LastChange):
    payload = {
        "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())),
        "air_temp": round(AirTemp,1),
        "pool_temp": round(PoolTemp,1),
        "solar_temp": round(SolarTemp,1),
        "return_temp": round(ReturnTemp,1),
        "lux": round(Lux,1),
        "pump": "ON" if PumpStatus==True else "OFF",
        "solar": "ON" if SolarStatus==True else "OFF",
        "last": LastChange
    }
    if 'mc' in globals():
        return mc.publish(config.mqtt_base_topic+"state", payload=json.dumps(payload))
    else:
        return

def publish_pump(status):
    payload = {
        "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())),
        "status": "ON" if status==True else "OFF"
    }
    return mc.publish(config.mqtt_base_topic+"pump", payload=json.dumps(payload))

def publish_solar(status):
    payload = {
        "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())),
        "status": "ON" if status==True else "OFF"
    }
    return mc.publish(config.mqtt_base_topic+"solar", payload=json.dumps(payload))

def publish_pump_cmd(cmd):
    return mc.publish(config.mqtt_base_topic+"pump/cmd", cmd)

def publish_solar_cmd(cmd):
    return mc.publish(config.mqtt_base_topic+"solar/cmd", cmd)
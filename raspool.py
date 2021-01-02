#!/usr/bin/python
import datetime, time, signal, sys, math
import logging
import threading
from collections import deque
from thermistor2temp import therm2temp
import Adafruit_ADS1x15
import RPi.GPIO as GPIO
import thread
import Adafruit_BMP.BMP085 as BMP085
from tsl2561 import TSL2561

import config
import hwconfig as HW
import lcd_display as DISPLAY
import mqtt as MQTT

#
# Startup
#
logging.basicConfig(filename='/var/log/raspool.log',level=logging.INFO,format='%(asctime)s %(message)s',datefmt='%Y-%m-%d %I:%M:%S %p')
logging.info('Raspool v1.1.0 starting')
DISPLAY.update(0, 'Raspool v1.1.0','(c) Burketech')

# Initialize the GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM) ## Use board pin numbering
GPIO.setup(HW.IO_Solar, GPIO.OUT)
GPIO.setup(HW.IO_Pump, GPIO.OUT)

# Luminosity Sensor (TLS2561)
lux_sensor = TSL2561()

# Air Temp (BMP180)
air_sensor = BMP085.BMP085()

# Initialise the ADC using the default mode (use default I2C address)
# Set this to ADS1015 or ADS1115 depending on the ADC you are using!
adc = Adafruit_ADS1x15.ADS1015()

# Ring buffer for storing multiple temperature readings, function to provide average
# http://stackoverflow.com/questions/4151320/efficient-circular-buffer
class CircularBuffer(deque):
	def __init__(self,size=0):
		super(CircularBuffer, self).__init__(maxlen=size)
	@property
	def average(self):
		return sum(self)/len(self)

def signal_handler(signal, frame):
	print 'You pressed Ctrl+C!'
	f.close()
	sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def ReadTemp(channel):
	volts = float(adc.read_adc(channel, gain=2)) / 1000
	if volts > 3.3:
		volts=3.3
	if volts == 0:
		volts=0.001
	ohms = round(((1/volts)*33000)-10000,0)

	return therm2temp[ohms]

LastSolarChange = 0
LastChange = "System startup"

AirTemps = CircularBuffer(size=10)
PoolTemps = CircularBuffer(size=10)
SolarTemps = CircularBuffer(size=10)
ReturnTemps = CircularBuffer(size=10)
Luxs = CircularBuffer(size=10)

AirTemp = 0
PoolTemp = 0
SolarTemp = 0
ReturnTemp = 0
Lux = 0

PumpStatus = GPIO.input(HW.IO_Pump)
SolarStatus = GPIO.input(HW.IO_Solar)

#
# A repeating thread to read the temp probes every n seconds
#
def get_temps():
    global AirTemp, PoolTemp, SolarTemp, ReturnTemp, Lux

    AirTemps.append(air_sensor.read_temperature() * 9/5 + 32)
    PoolTemps.append(ReadTemp(HW.ADC_Pool))
    SolarTemps.append(ReadTemp(HW.ADC_Solar))
    ReturnTemps.append(ReadTemp(HW.ADC_Return))
    Luxs.append(lux_sensor.lux())

    AirTemp = AirTemps.average
    PoolTemp = PoolTemps.average
    SolarTemp = SolarTemps.average
    ReturnTemp = ReturnTemps.average
    Lux = Luxs.average

    DISPLAY.update(1, 'Pool      {:5.1f}F'.format(PoolTemp), 'Solar     {:5.1f}F'.format(SolarTemp))
    DISPLAY.update(2, 'Return    {:5.1f}F'.format(ReturnTemp), 'Air Temp  {:5.1f}F'.format(AirTemp))
    #DISPLAY.update(3, 'Air Temp  {:5.1f}F'.format(AirTemp),  'Lux        {:4d}'.format(Lux))

    # Start threading this every n seconds
    threading.Timer(config.TEMP_REFRESH, get_temps).start()

threading.Thread(target=get_temps).start()

#
# A repeating thread to refresh the LCD display every n seconds
#
def refresh_display():
    DISPLAY.show_next()
    threading.Timer(config.LCD_REFRESH, refresh_display).start()

threading.Thread(target=refresh_display).start()

#
# A repeating thread to log status to MQTT
#
def log_status():
    # Dont log until we have at least the air temp captured
    if (AirTemp != 0):
        MQTT.publish_status(AirTemp, PoolTemp, SolarTemp, ReturnTemp, Lux, PumpStatus, SolarStatus, LastChange)

    threading.Timer(config.LOGGING_REFRESH, log_status).start()

threading.Thread(target=log_status).start()

#
# Command to force status update
#
def state_cmd(client, userdata, message):
	MQTT.publish_status(AirTemp, PoolTemp, SolarTemp, ReturnTemp, Lux, PumpStatus, SolarStatus, LastChange)

#
# Control the water pump
#
def pump_cmd(client, userdata, message):
    global PumpStatus
    if (message.payload == "ON"):
        PumpStatus = 1
        GPIO.output(HW.IO_Pump,True)
        MQTT.publish_pump(True)
        DISPLAY.show_now("Pump ON", "")
    elif (message.payload == "OFF"):
        PumpStatus = 0
        GPIO.output(HW.IO_Pump,False)
        MQTT.publish_pump(False)
        DISPLAY.show_now("Pump OFF", "")
    else:
        logging.warning("Unknown pump cmd %s" % message.payload)

#
# Control the solar heater
#
def solar_cmd(client, userdata, message):
    global SolarStatus
    if (message.payload == "ON"):
        SolarStatus = 1
        GPIO.output(HW.IO_Solar,True)
        MQTT.publish_solar(True)
        DISPLAY.show_now("Solar ON", "")
    elif (message.payload == "OFF"):
        SolarStatus = 0
        GPIO.output(HW.IO_Solar,False)
        MQTT.publish_solar(False)
        DISPLAY.show_now("Solar OFF", "")
    else:
        logging.warning("Unknown solar cmd %s" % message.payload)

#
# MAIN
#

# Subscribe to MQTT messages
mqtt_client = MQTT.init((("state/cmd",state_cmd),("pump/cmd",pump_cmd),("solar/cmd",solar_cmd)))

while True:
	#
	# Get the data
	#
	Now = time.time()
	PumpStatus = GPIO.input(HW.IO_Pump)
	SolarStatus = GPIO.input(HW.IO_Solar)
	DISPLAY.update(3, 'Pump         {:>3}'.format('On' if PumpStatus==1 else 'Off'), 'Solar        {:>3}'.format('On' if SolarStatus==1 else 'Off'))

	#
	# Control Logic
	#

	# Dont change until we have at least the pool temp captured
	if (PoolTemp != 0):

		# Pump & solar are on & pool temp at or above set maximum - turn OFF solar
		if (PumpStatus == 1 and SolarStatus == 1 and PoolTemp >= config.POOL_MAX_TEMP):
			if (Now-LastSolarChange > config.SOLAR_CHANGE_FREQUENCY):
				LastChange = "Pool at or above target temperature - turning off solar"
				MQTT.publish_solar_cmd("OFF")
				LastSolarChange = Now

		# Pump & solar are on & pool temp at or above solar temp - turn OFF solar
		if (PumpStatus == 1 and SolarStatus == 1 and PoolTemp >= SolarTemp):	
			if (Now-LastSolarChange > config.SOLAR_CHANGE_FREQUENCY):
				LastChange = "Pool at or above solar temperature - turning off solar"
				MQTT.publish_solar_cmd("OFF")
				LastSolarChange = Now

		# Pump is on & solar is off & pool temp below set maximum & solar above pool temp by threshold - turn ON solar
		if (PumpStatus == 1 and SolarStatus == 0 and PoolTemp < config.POOL_MAX_TEMP and SolarTemp-PoolTemp > config.SOLAR_POOL_DIFF):
			if (Now-LastSolarChange > config.SOLAR_CHANGE_FREQUENCY):
				LastChange = "Pool below target temperature and solar differential reached - turning on solar"
				MQTT.publish_solar_cmd("ON")
				LastSolarChange = Now

		# Pump is off & solar is on - turn OFF solar
		if (PumpStatus == 0 and SolarStatus == 1):
			if (Now-LastSolarChange > config.SOLAR_CHANGE_FREQUENCY):
				LastChange = "Pool pump off - turning off solar"
				MQTT.publish_solar_cmd("OFF")
				LastSolarChange = Now

	#
	# Keypad Button Logic
	#
	if DISPLAY.is_up_pressed():
		MQTT.publish_pump_cmd("ON")

	if DISPLAY.is_down_pressed():
		MQTT.publish_pump_cmd("OFF")

	if DISPLAY.is_right_pressed():
		MQTT.publish_solar_cmd("ON")

	if DISPLAY.is_left_pressed():
		MQTT.publish_solar_cmd("OFF")

	# Check for any MQTT messages to send or process

	mqtt_client.loop()

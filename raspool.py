#!/usr/bin/python
import datetime, time, signal, sys, math
import threading
from collections import deque
from thermistor2temp import therm2temp
import Adafruit_ADS1x15
import RPi.GPIO as GPIO
import thread
import Adafruit_BMP.BMP085 as BMP085
from tsl2561 import TSL2561

import config
import lcd_display as DISPLAY
import log_to_google as GLOG
import log_to_dweet as DLOG

IO_Solar = 17
IO_Pump = 18
ADC_Pool = 0
ADC_Solar = 1

PoolMaxTemp = 90
SolarPoolDiff = 5
SolarChangeFrequency = 5 * 60
DisplayUpdateFrequency = 5
SensorUpdateFrequency = 1
LogUpdateFrequency = 5 * 60

#
# Startup
#
DISPLAY.update(0, 'Raspool v1.0.0','(c) Burketech')

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM) ## Use board pin numbering
GPIO.setup(IO_Solar, GPIO.OUT)
GPIO.setup(IO_Pump, GPIO.OUT)

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

# Open a logging file
f = open("/var/log/pool.log", "a+")

LastSolarChange = 0
LastSensorUpdate = 0
LastLog = "System startup"
LastLogUpdate = 0

AirTemps = CircularBuffer(size=10)
PoolTemps = CircularBuffer(size=10)
SolarTemps = CircularBuffer(size=10)
Luxs = CircularBuffer(size=10)

AirTemp = 0
PoolTemp = 0
SolarTemp = 0
Lux = 0

PumpStatus = GPIO.input(IO_Pump)
SolarStatus = GPIO.input(IO_Solar)

#
# A repeating thread to read the temp probes every n seconds
#
def get_temps():
    global AirTemp, PoolTemp, SolarTemp, Lux

    AirTemps.append(air_sensor.read_temperature() * 9/5 + 32)
    PoolTemps.append(ReadTemp(ADC_Pool))
    SolarTemps.append(ReadTemp(ADC_Solar))
    Luxs.append(lux_sensor.lux())
    LastSensorUpdate = Now

    AirTemp = AirTemps.average
    PoolTemp = PoolTemps.average
    SolarTemp = SolarTemps.average
    Lux = Luxs.average

    DISPLAY.update(1, 'Pool      {:5.1f}F'.format(PoolTemp), 'Solar     {:5.1f}F'.format(SolarTemp))
    DISPLAY.update(2, 'Air Temp  {:5.1f}F'.format(AirTemp),  'Lux        {:4d}'.format(Lux))

    DLOG.dweet_update_temps(AirTemp,PoolTemp,SolarTemp,Lux)

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
# A repeating thread to update the equipment status
#
def update_equipment():
    global PumpStatus, SolarStatus

    PumpStatus = GPIO.input(IO_Pump)
    SolarStatus = GPIO.input(IO_Solar)

    DISPLAY.update(3, 'Pump         {:>3}'.format('On' if PumpStatus==1 else 'Off'), 'Solar        {:>3}'.format('On' if SolarStatus==1 else 'Off'))
    DLOG.dweet_update_equipment(PumpStatus,SolarStatus)

    threading.Timer(config.EQUIP_REFRESH, update_equipment).start()

threading.Thread(target=update_equipment).start()

#
# MAIN
#

while True:
	#
	# Get the data
	#
	Now = time.time()
#	PumpStatus = GPIO.input(IO_Pump)
#	SolarStatus = GPIO.input(IO_Solar)

	#
	# Control Logic
	#
	if (PumpStatus == 1 and SolarStatus == 1 and PoolTemp > PoolMaxTemp):
		if (Now-LastSolarChange > SolarChangeFrequency):
			LastLog = "Pool at or above target temperature - turning off solar"
			GPIO.output(IO_Solar,False)
			LastSolarChange = Now
			LastLogUpdate = 0
	if (PumpStatus == 1 and SolarStatus == 1 and PoolTemp >= SolarTemp):
		if (Now-LastSolarChange > SolarChangeFrequency):
			LastLog = "Pool at or above solar temperature - turning off solar"
			GPIO.output(IO_Solar,False)
			LastSolarChange = Now
			LastLogUpdate = 0
	if (PumpStatus == 1 and SolarStatus == 0 and PoolTemp < PoolMaxTemp and SolarTemp-PoolTemp > SolarPoolDiff):
		if (Now-LastSolarChange > SolarChangeFrequency):
			LastLog = "Pool below target temperature and solar differential reached - turning on solar"
			GPIO.output(IO_Solar,True)
			LastSolarChange = Now
			LastLogUpdate = 0
	if (PumpStatus == 0 and SolarStatus == 1):
		if (Now-LastSolarChange > SolarChangeFrequency):
			LastLog = "Pool pump off - turning off solar"
			GPIO.output(IO_Solar,False)
			LastSolarChange = Now
			LastLogUpdate = 0

	#
	# Logging Logic
	#
	if (Now-LastLogUpdate > LogUpdateFrequency):
		LogMessage = "%d,%d,%d,%d,%d,%d,%d,%s\n" % (Now,PumpStatus,SolarStatus,AirTemp,PoolTemp,SolarTemp,Lux,LastLog)
		f.write(LogMessage)
		f.flush()

		GLOG.log_temps_to_google(datetime.datetime.now(),PumpStatus,SolarStatus,AirTemp,PoolTemp,SolarTemp,Lux,LastLog)

		LastLog = ""
		LastLogUpdate = Now

	#
	# Keypad Button Logic
	#
	if DISPLAY.is_up_pressed():
		GPIO.output(IO_Pump,True)

	if DISPLAY.is_down_pressed():
		GPIO.output(IO_Pump,False)

	if DISPLAY.is_right_pressed():
		GPIO.output(IO_Solar,True)

	if DISPLAY.is_left_pressed():
		GPIO.output(IO_Solar,False)

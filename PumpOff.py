#!/usr/bin/python
import RPi.GPIO as GPIO ## Import GPIO library
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.OUT)
GPIO.output(18,False)

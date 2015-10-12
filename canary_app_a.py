#!/usr/bin/env python
# canary_app.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName = "canary_app" 

import sys
import os
import time
from cbcommslib import CbApp
from cbconfig import *
import requests
import json
from twisted.internet import reactor

SEND_DELAY               = 5      # Time to gather values before sending them
CONNECT_SEND_INTERVAL    = 10800  # 3 hours

# Default values:
config = {
    "temperature": "True",
    "temp_min_change": 0.2,
    "humidity": "True",
    "humidity_min_change": 0.2,
    "binary": "True",
    "buttons": "True",
    "luminance": "True",
    "luminance_min_change": 1.0,
    "battery": "True",
    "battery_min_change": 1.0,
    "connected": "True",
    "temperature_interval": 600.0,
    "humidity_interval": 1800.0,
    "luminance_interval": 1800.0,
    "cid": "CID63"
}

def state2int(s):
    if s == "on":
        return 1
    else:
        return 0

class DataManager:
    """ Managers data storage for all sensors """
    def __init__(self, aid):
        self.waiting = False
        self.aid = aid
        self.seq = 0
        self.store = [] 
        self.connected = False
        self.endToEnd = False

    def getseq(self, init=False):
        if init:
            self.seq = 0
        else:
            self.seq += 1
        return self.seq

    def manageConnect(self, connected):
        self.connected = connected
        if connected == True:
            msg = {
                   "source": self.aid,
                   "destination": config["cid"],
                   "body": {"n":self.getseq()} 
                  }
            self.sendMessage(msg, "conc")
            self.cbLog("debug", "manageConnect. Sending " + str(json.dumps(msg, indent=4)))
        else:
            self.endToEnd = False

    def sendValues(self):
        self.waiting = False
        body = {
                "n": self.getseq(),
                "d": self.store
               }
        self.store = []
        msg = {
               "source": self.aid,
               "destination": config["cid"],
               "body": body,
              }
        self.cbLog("debug", "sendValues. Sending " + str(json.dumps(msg, indent=4)))
        self.sendMessage(msg, "conc")

    def processAck(self, ack):
        pass

    def storeValues(self, values):
        self.store.append(values)
        if not self.waiting:
            reactor.callLater(SEND_DELAY, self.sendValues)
            self.waiting = True

class TemperatureMeasure():
    """ Either send temp every minute or when it changes. """
    def __init__(self, id):
        self.id = id
        epochTime = time.time()
        self.prevTemp = -100.0

    def process(self, message):
        timeStamp = int(message["timeStamp"])
        temp = message["data"]
        self.cbLog("debug", "process temperature, data: " + temp)
        if abs(temp-self.prevTemp) >= config["temp_min_change"]:
            self.prevTemp = temp
            self.dm.storeValues({"i": self.id, "t":temp, "s":timeStamp})

class Humid():
    """ Either send temp every minute or when it changes. """
    def __init__(self, id):
        self.id = id
        self.previous = 0.0

    def process(self, message):
        h = message["data"]
        timeStamp = int(message["timeStamp"])
        if abs(h-self.previous) >= config["humidity_min_change"]:
            self.dm.storeValues({"i": self.id, "h":h, "s":timeStamp})
            self.previous = h

class Binary():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def process(self, message):
        timeStamp = int(message["timeStamp"])
        b = message["data"]
        self.cbLog("debug", "process Binary, data: " + b)
        bi = state2int(b)
        if bi != self.previous:
            self.dm.storeValues({"i": self.id, "b":bi, "s":timeStamp})
            self.previous = bi

class Buttons():
    def __init__(self, id):
        self.id = id

    def process(self, message):
        timeStamp = int(message["timeStamp"])
        for key, value in message["data"].iteritems():
            val = state2int(value)
            self.dm.storeValues({"i": self.id, ('b'+key):val, "s":timeStamp})

class Luminance():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def process(self, message):
        v = message["data"]
        timeStamp = int(message["timeStamp"])
        if abs(v-self.previous) >= config["luminance_min_change"]:
            self.dm.storeValues({"i": self.id, "l":v, "s":timeStamp})
            self.previous = v

class Battery():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def process(self, message):
        v = message["data"]
        timeStamp = int(message["timeStamp"])
        if abs(v-self.previous) >= config["battery_min_change"]:
            self.dm.storeValues({"i": self.id, "bt":v, "s":timeStamp})
            self.previous = v

class Connected():
    def __init__(self, id):
        self.id = id
        self.previous = 0
        self.lastSent = 0

    def process(self, resp):
        v = resp["data"]
        timeStamp = resp["timeStamp"] 
        if v:
            b = 1
        else:
            b = 0
        if b != self.previous or timeStamp - self.lastSent > CONNECT_SEND_INTERVAL:
            self.dm.storeValues({"i": self.id, "c":b, "s":timeStamp})
            self.previous = b
            self.lastSent = timeStamp

class App(CbApp):
    def __init__(self, argv):
        self.state = "stopped"
        self.concConnected = False
        self.bridgeConnected = False
        self.temp = []
        self.humidity = []
        self.binary = []
        self.buttons = []
        self.luminance = []
        self.battery = []
        self.connected = []
        self.devices = []
        self.idToName = {} 
        self.switchTimes = []
        self.boilerID = "unknown"
        reactor.callLater(30, self.switchBoiler)
        #CbApp.__init__ MUST be called
        CbApp.__init__(self, argv)

    def setState(self, action):
        if action == "clear_error":
            self.state = "running"
        else:
            self.state = action
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def switchBoiler(self):
        if self.switchTimes != []:
            dones = []
            for s in self.switchTimes:
                if time.time() > s["at"]:
                    command = {"id": self.id,
                               "request": "command"}
                    if s["s"] == 1:
                        command["data"] = "on"
                    else:
                        command["data"] = "off"
                    self.cbLog("debug", "switchBoiler, command: " + str(command))
                    if self.boilerID != "unknown":
                        self.sendMessage(command, self.boilerID)
                    else:
                        self.cbLog("warning", "switchBoiler, Attempting to switch unconnected boiler")
                    dones.append(s["at"])
            self.switchTimes = [s for s in self.switchTimes if s["at"] not in dones]
        reactor.callLater(5, self.switchBoiler)

    def onConcMessage(self, msg):
        self.cbLog("debug", "onConcMessage, message: " + str(json.dumps(msg, indent=4)))
        if "resp" in msg:
            self.concConnected = True
            if self.bridgeConnected:
                self.dm.manageConnect(True)
        elif "body" in msg:
            # If we receive a switch command, write it to the switch file
            try: 
                for b in msg["body"]["d"]:
                    self.cbLog("debug", "onConcMessage. b: " + str( b))
                    if "s" in b and "at" in b:
                        self.switchTimes.append(b)
            except Exception as ex:
                self.cbLog("warning", "Unexpected message body processing d. Exception: " + str(type(ex)) + ", " + str(ex.args))
            try: 
                if "a" in msg["body"]:
                    self.dm.processAck(msg["body"]["a"])
            except Exception as ex:
                self.cbLog("warning", "Unexpected message body processing a. Exception: " + str(type(ex)) + ", " + str(ex.args))
        else: 
            self.cbLog("warning", "onConcMessage, No body in message: " + str(json.dumps(msg, indent=4)))

    def onAdaptorData(self, message):
        """
        This method is called in a thread by cbcommslib so it will not cause
        problems if it takes some time to complete (other than to itself).
        """
        self.cbLog("debug", "onAdaptorData, message: " + str(json.dumps(message, indent=4)))
        if message["characteristic"] == "temperature":
            for t in self.temp:
                if t.id == self.idToName[message["id"]]:
                    t.process(message)
                    break
        elif message["characteristic"] == "humidity":
            for b in self.humidity:
                if b.id == self.idToName[message["id"]]:
                    b.process(message)
                    break
        elif message["characteristic"] == "binary_sensor":
            for b in self.binary:
                if b.id == self.idToName[message["id"]]:
                    b.process(message)
                    break
        elif message["characteristic"] == "number_buttons":
            for b in self.buttons:
                if b.id == self.idToName[message["id"]]:
                    b.process(message)
                    break
        elif message["characteristic"] == "battery":
            for b in self.battery:
                if b.id == self.idToName[message["id"]]:
                    b.process(message)
                    break
        elif message["characteristic"] == "connected":
            for b in self.connected:
                if b.id == self.idToName[message["id"]]:
                    b.process(message)
                    break
        elif message["characteristic"] == "luminance":
            for b in self.luminance:
                if b.id == self.idToName[message["id"]]:
                    b.process(message)
                    break

    def onAdaptorService(self, message):
        self.cbLog("debug", "onAdaptorService, message: " + str(json.dumps(message, indent=4)))
        serviceReq = []
        for p in message["service"]:
            # Based on services offered & whether we want to enable them
            if p["characteristic"] == "temperature":
                if config["temperature"] == 'True':
                    self.temp.append(TemperatureMeasure((self.idToName[message["id"]])))
                    self.temp[-1].dm = self.dm
                    self.temp[-1].cbLog = self.cbLog
                    serviceReq.append({"characteristic": "temperature",
                                       "interval": config["temperature_interval"]})
            elif p["characteristic"] == "humidity":
                if config["humidity"] == 'True':
                    self.humidity.append(Humid(self.idToName[message["id"]]))
                    self.humidity[-1].dm = self.dm
                    serviceReq.append({"characteristic": "humidity",
                                       "interval": config["humidity_interval"]})
            elif p["characteristic"] == "binary_sensor":
                if config["binary"] == 'True':
                    self.binary.append(Binary(self.idToName[message["id"]]))
                    self.binary[-1].dm = self.dm
                    self.binary[-1].cbLog = self.cbLog
                    serviceReq.append({"characteristic": "binary_sensor",
                                       "interval": 0})
            elif p["characteristic"] == "number_buttons":
                if config["buttons"] == 'True':
                    self.buttons.append(Buttons(self.idToName[message["id"]]))
                    self.buttons[-1].dm = self.dm
                    serviceReq.append({"characteristic": "number_buttons",
                                       "interval": 0})
            elif p["characteristic"] == "battery":
                if config["battery"] == 'True':
                    self.battery.append(Battery(self.idToName[message["id"]]))
                    self.battery[-1].dm = self.dm
                    serviceReq.append({"characteristic": "battery",
                                       "interval": 0})
            elif p["characteristic"] == "connected":
                if config["connected"] == 'True':
                    self.connected.append(Connected(self.idToName[message["id"]]))
                    self.connected[-1].dm = self.dm
                    serviceReq.append({"characteristic": "connected",
                                       "interval": 0})
            elif p["characteristic"] == "luminance":
                if config["luminance"] == 'True':
                    self.luminance.append(Luminance(self.idToName[message["id"]]))
                    self.luminance[-1].dm = self.dm
                    serviceReq.append({"characteristic": "luminance",
                                       "interval": config["luminance_interval"]})
            elif p["characteristic"] == "switch":
                self.boilerID = message["id"]
                serviceReq.append({"characteristic": "switch", 
                                   "interval": 0})
        msg = {"id": self.id,
               "request": "service",
               "service": serviceReq}
        self.sendMessage(msg, message["id"])
        self.setState("running")

    def onConfigureMessage(self, configMessage):
        """ Config is based on what sensors are available """
        for adaptor in configMessage["adaptors"]:
            adtID = adaptor["id"]
            if adtID not in self.devices:
                # Because configure may be re-called if devices are added
                name = adaptor["name"]
                friendly_name = adaptor["friendly_name"]
                self.cbLog("debug", "Configure app. Adaptor name: " + name)
                self.idToName[adtID] = friendly_name.replace(" ", "_")
                self.devices.append(adtID)
        self.dm = DataManager(self.id)
        self.dm.sendMessage = self.sendMessage
        self.dm.cbLog = self.cbLog
        configFile = CB_CONFIG_DIR + "canary_app.config"
        global config
        try:
            with open(configFile, 'r') as configFile:
                newConfig = json.load(configFile)
                self.cbLog("info", "Read canary_app.config")
                config.update(newConfig)
        except Exception as ex:
            self.cbLog("warning", "canary_app.config does not exist or file is corrupt. Exception: " + str(type(ex)) + ", " +  str(ex.args))
        for c in config:
            if c.lower in ("true", "t", "1"):
                config[c] = True
            elif c.lower in ("false", "f", "0"):
                config[c] = False
        self.cbLog("debug", "Config: " + str(json.dumps(config, indent=4)))
        self.setState("starting")

    def onManagerStatus(self, connected):
        self.bridgeConnected = connected
        if connected:
            if self.concConnected:
                self.dm.manageConnect(True)
        else:
            self.dm.manageConnect(False)

if __name__ == '__main__':
    App(sys.argv)

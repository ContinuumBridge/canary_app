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
import logging
from cbcommslib import CbApp
from cbconfig import *
import requests
import json
from twisted.internet import reactor

CID                      = "CID1"
SEND_DELAY               = 10  # Time to gather values before sending them

# Default values:
config = {
    'temperature': 'True',
    'temp_min_change': 0.2,
    'humidity': 'True',
    'humidity_min_change': 0.2,
    'binary': 'True',
    'luminance': 'True',
    'luminance_min_change': 1.0,
    'battery': 'True',
    'battery_min_change': 1.0,
    'connected': 'True',
    'slow_polling_interval': 600.0
    'cid': 'XX'
}

class DataManager:
    """ Managers data storage for all sensors """
    def __init__(self, aid, cid):
        self.waiting = False
        self.aid = aid
        self.seq = 0
        CID = cid
        self.store = [] 
        self.connected = False
        self.endToEnd = False

    def getseq(self, init=False):
        if init:
            self.seq = 0
        else:
            try:
                with open(SEQFILE, 'r') as f:
                    self.seq = f.read()
                    self.seq +=
            except:
                self.seq = 0
                logging.warning('%s getseq. Could not open SEQFILE', ModuleName)
        with open(SEQFILE, 'r') as f:
            f.write(seq)
        return self.seq

    def manageConnect(self, connected):
        self.connected = connected
        if connected == True:
            msg = {
                   "source": self.aid,
                   "destination": CID,
                   "body": {"n":getseq()} 
                  }
            self.sendMessage(msg, "conc")
        else:
            self.endToEnd = False

    def sendValues(self):
        self.waiting = False
        body = {
                "n": self.seq,
                "d": self.store
               }
        del self.store
        try:
            with open(STOREFILE, 'r') as f:
                store = json.load(f)
        except:
            logging.warning('%s sendValue. Could not open %s', ModuleName, STOREFILE)
        store.append(body)
        try:
            with open(STOREFILE, 'w') as f:
                json.dump(store, f)
        except:
            logging.warning('%s sendValue. Could not open %s', ModuleName, STOREFILE)
        msg = {
               "source": self.aid,
               "destination": CID,
               "body": body,
              }
        self.sendMessage(msg, "conc")

    def processAck(self, ack):
        self.endToEnd = True
        try:
            with open(STOREFILE, 'r') as f:
                store = json.load(f)
        except:
            logging.warning('%s processAck. Could not open store file', ModuleName)
        for s in store:
            if s["s"] < self.seq:
                store.remove(s)
        try:
            with open(storeFile, 'w') as f:
                json.dump(store, f)
        except:
            logging.warning('%s storeValue. Could not write store to file', ModuleName)

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
        self.prevTemp = -100

    def process(self, message):
        timeStamp = message["timeStamp"] 
        temp = message["data"]
        if abs(temp-self.prevTemp) >= config["temp_min_change"]:
            self.dm.storeTemp(self.id, timeStamp, temp) 
            self.prevTemp = temp
            self.dm.storeValues({"i": self.id, "t":temp, "s":timeStamp})

class Humid():
    """ Either send temp every minute or when it changes. """
    def __init__(self, id):
        self.id = id
        self.previous = 0.0

    def process(self, message):
        h = message["data"]
        timeStamp = message["timeStamp"] 
        if abs(h-self.previous) >= config["humidity_min_change"]:
            self.dm.storeValues({"i": self.id, "h":h, "s":timeStamp})
            self.previous = h

class Binary():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def process(self, message):
        timeStamp = message["timeStamp"] 
        b = message["data"]
        if b == "on":
            bi = 1
        else:
            bi = 0
        if bi != self.previous:
            self.dm.storeValues({"i": self.id, "b":bi, "s":timeStamp})
            self.previous = bi

class Luminance():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def process(self, message):
        v = message["data"]
        timeStamp = message["timeStamp"] 
        if abs(v-self.previous) >= config["luminance_min_change"]:
            self.dm.storeValues({"i": self.id, "l":v, "s":timeStamp})
            self.previous = v

class Battery():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def process(self, message):
        v = message["data"]
        timeStamp = message["timeStamp"] 
        if abs(v-self.previous) >= config["battery_min_change"]:
            self.dm.storeValues({"i": self.id, "bt":v, "s":timeStamp})
            self.previous = v

class Connected():
    def __init__(self, id):
        self.id = id
        self.previous = 0

    def process(self, resp):
        v = resp["data"]
        timeStamp = resp["timeStamp"] 
        if v:
            b = 1
        else:
            b = 0
        if b != self.previous:
            self.dm.storeValues({"i": self.id, "c":b, "s":timeStamp})
            self.previous = b

class App(CbApp):
    def __init__(self, argv):
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(message)s')
        self.state = "stopped"
        self.concConnected = False
        self.bridgeConnected = False
        configFile = CB_CONFIG_DIR + "canary_app.config"
        global config
        try:
            with open(configFile, 'r') as configFile:
                newConfig = json.load(configFile)
                logging.info('%s Read canary_app.config', ModuleName)
                config.update(newConfig)
        except:
            logging.warning('%s canary_app.config does not exist or file is corrupt', ModuleName)
        for c in config:
            if c.lower in ("true", "t", "1"):
                config[c] = True
            elif c.lower in ("false", "f", "0"):
                config[c] = False
        logging.debug('%s Config: %s', ModuleName, config)
        self.temp = []
        self.humidity = []
        self.binary = []
        self.luminance = []
        self.battery = []
        self.connected = []
        self.devices = []
        self.idToName = {} 
        #CbApp.__init__ MUST be called
        CbApp.__init__(self, argv)

    def setState(self, action):
        if action == "clear_error":
            self.state = "running"
        else:
            self.state = action
        logging.debug("%s state: %s", ModuleName, self.state)
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)


    def onConcMessage(self, msg):
        logging.debug("%s resp from conc: %s", ModuleName, resp)
        if "resp" in msg:
            self.concConnected = True
            if self.bridgeConnected:
                self.dm.manageConnect(True)
        elif "body" in msg:
            # If we receive a switch command, write it to the switch file
            if "s" in msg["body"] and "at" in msg["body"]:
                try:
                    with open(switchFile, 'r') as f:
                        switchTimes = json.load(f)
                except:
                    switchTimes = []
                switchTimes.append({msg["body"]["s"]: msg["body"]["at"]})
                try:
                    with open(switchFile, 'w') as f:
                        json.dump(switchTimes, f)
                except:
                    logging.warning('%s onConcMessage. Could not write switchTimes to file', ModuleName)
            if "a" in msg["body"]:
                self.dm.processAck(msg["body"]["a"])
        else: 
            logging.debug('%s onConcMessage. No body in message: %s', ModuleName, msg)

    def onAdaptorData(self, message):
        """
        This method is called in a thread by cbcommslib so it will not cause
        problems if it takes some time to complete (other than to itself).
        """
        #logging.debug("%s onadaptorData, message: %s", ModuleName, message)
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
        #logging.debug("%s onAdaptorService, message: %s", ModuleName, message)
        serviceReq = []
        for p in message["service"]:
            # Based on services offered & whether we want to enable them
            if p["characteristic"] == "temperature":
                if config["temperature"] == 'True':
                    self.temp.append(TemperatureMeasure((self.idToName[message["id"]])))
                    self.temp[-1].dm = self.dm
                    serviceReq.append({"characteristic": "temperature",
                                       "interval": config["slow_polling_interval"]})
            elif p["characteristic"] == "humidity":
                if config["humidity"] == 'True':
                    self.humidity.append(Humid(self.idToName[message["id"]]))
                    self.humidity[-1].dm = self.dm
                    serviceReq.append({"characteristic": "humidity",
                                       "interval": config["slow_polling_interval"]})
            elif p["characteristic"] == "binary_sensor":
                if config["binary"] == 'True':
                    self.binary.append(Binary(self.idToName[message["id"]]))
                    self.binary[-1].dm = self.dm
                    serviceReq.append({"characteristic": "binary_sensor",
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
                                       "interval": 0})
        msg = {"id": self.id,
               "request": "service",
               "service": serviceReq}
        self.sendMessage(msg, message["id"])
        self.setState("running")

    def onConfigureMessage(self, config):
        """ Config is based on what sensors are available """
        for adaptor in config["adaptors"]:
            adtID = adaptor["id"]
            if adtID not in self.devices:
                # Because configure may be re-called if devices are added
                name = adaptor["name"]
                friendly_name = adaptor["friendly_name"]
                logging.debug("%s Configure app. Adaptor name: %s", ModuleName, name)
                self.idToName[adtID] = friendly_name.replace(" ", "_")
                self.devices.append(adtID)
        self.dm = DataManager(self.bridge_id)
        self.setState("starting")

    def onManagerStatus(self, status):
        if status == "connected":
            self.bridgeConnected = True
            if self.concConnected:
                self.dm.manageConnect(True)
        elif status == "disconnected":
            self.bridgeConnected = False
            self.dm.manageConnect(False)

if __name__ == '__main__':
    App(sys.argv)
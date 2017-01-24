#!/usr/bin/env python3

import os
import threading
from datetime import datetime
from time import sleep
import paho.mqtt.client as mqttSub
import paho.mqtt.publish as mqttPub
import xml.etree.ElementTree as ET
import requests
from xml.dom import minidom


# Global vars
mqttServer = '<name_or_ip>'
mqttTopic = '/hifi/'
hifiIp = '<name_or_ip>'
logFile = '/var/log/mqtt_hifi'
refreshPeriod = 10
refreshCount = 0
httpTimeout = (2, 6)    # Connect, Read    
debug = False
currentStatus = {
    'power': '',
    'source': '',
    'mute': '',
    'volume': 0,
    'band': '',
    'playing': '',
    'favorite': '',
}
cmd_queue = []


# Hifi vars
maxVol = 60
statUrl = 'http://' + hifiIp + '/goform/AppCommand.xml'
httpHeaders = {
    'Content-Type': 'text/xml; charset="utf-8"',
    }
basicStats='<?xml version="1.0" encoding="utf-8" ?><tx><cmd id="1">GetAllZonePowerStatus</cmd><cmd id="1">GetVolumeLevel</cmd><cmd id="1">GetMuteStatus</cmd><cmd id="1">GetSourceStatus</cmd></tx>'
tunerStats='<?xml version="1.0" encoding="utf-8" ?><tx><cmd id="1">GetTunerStatus</cmd></tx>'
netStats='<?xml version="1.0" encoding="utf-8" ?><tx><cmd id="1">GetNetAudioStatus</cmd></tx>'
powerMap = {
    'ON': 'PowerOn',
    'OFF': 'PowerStandby',
}
muteMap = {
    'ON': 'MuteOn',
    'OFF': 'MuteOff',
}

##      Logging

def log(msg):
    logTs = datetime.now().strftime('%d/%m/%y %H:%M:%S')
    if debug is True:
        print(logTs + ' ' + msg)
    lf = open(logFile, 'a')
    lf.write(logTs + ' ' + msg + '\n')
    lf.close()

##
##      Hifi communication
##

def hifiFetch(data):
    try:
        r = requests.post(url=statUrl, data=data, headers=httpHeaders, timeout=httpTimeout)
        if (r.status_code != requests.codes.ok):
            log(url + ' returned ' + r.status_code)
            return None
        else:
            return ET.fromstring(r.text)
    except Exception as ex:
        log('Failed to fetch ' + statUrl)
        return None 

def hifiStatus():
    # Fetch basic status
    root = hifiFetch(basicStats)
    if root is not None:
        hs = {
            'power': 'OFF' if root.find('.//zone1').text == 'STANDBY' else 'ON',
            'source': root.find('.//source').text if root.find('.//source') is not None else '',
            'mute': root.find('.//mute').text.upper(),
            'volume': str(int(int(root.find('.//dispvalue').text) / 60 * 100)),    # Convert to percent
            'band': '',
            'playing': '',
        }
        # Fetch source specific status
        if hs['source'] == 'Internet Radio':
            root = hifiFetch(netStats)
            if root is not None and root.find('.//*[@id="track"]') is not None:
                hs['playing'] = root.find('.//*[@id="track"]').text
        if hs['source'] == 'TUNER':
            root = hifiFetch(tunerStats)
            if root is not None and root.find('.//band') is not None:
                hs['band'] = root.find('.//band').text
                hs['playing'] = root.find('.//frequency').text
        # Update & publish any changes
        items = ['power', 'source', 'mute', 'volume', 'band', 'playing']
        for i in items:
            if currentStatus[i] != hs[i]:
                currentStatus[i] = hs[i]
                log('Status of ' + i + ' changed to ' + hs[i])
                mqttPub.single(mqttTopic + i, hs[i], hostname=mqttServer)
    if (debug):
        log('Refreshed status from ' + hifiIp)

def hifiSync():
    global refreshCount
    refreshCount += 1
    if len(cmd_queue) > 0:
        # Send a queued command
        url = cmd_queue.pop(0)
        if (debug):
            log('Sending ' + url)
        try:
            r = requests.get(url, timeout=httpTimeout)
            if (r.status_code != requests.codes.ok):
                log(url + ' returned ' + r.status_code)
        except requests.exceptions.RequestException as e:
            log(url + ' failed: ' + e)
        if powerMap['ON'] in url:
            log('sleeping')
            sleep(4)    # Let it 'warm up' before sending anything else
    else:
        if refreshCount >= refreshPeriod:
            hifiStatus()
            refreshCount = 0
    threading.Timer(1, hifiSync).start()

##      Queue a command to the Hifi

def hifiSend(func, command):
    baseUrl = 'http://' + hifiIp + '/goform/'
    url = None
    if func == 'power':
        if command not in powerMap:
            log('Invalid argument ' + command + ' for ' + func)
            return 
        url = baseUrl + 'formiPhoneAppPower.xml?1+' + powerMap[command]
        currentStatus[func] = command
    if func == 'mute':
        if command not in muteMap:
            log('Invalid argument ' + command + ' for ' + func)
            return
        url = baseUrl + 'formiPhoneAppMute.xml?1+' + muteMap[command]
        currentStatus[func] = command
    if func == 'band':
        if command not in ['DA', 'FM']:
            log('Invalid argument ' + command + ' for ' + func)
            return
        url = baseUrl + 'formiPhoneAppTuner.xml?1+' + command
        currentStatus[func] = command
    if func == 'source':
        if command not in ['TUNER', 'IRADIO']:
            log('Invalid argument ' + command + ' for ' + func)
            return
        url = baseUrl + 'formiPhoneAppDirect.xml?SI' + command
        currentStatus[func] = command
    if func == 'volume' and int(command) > 0:
        vol = int(int(command) / 100 * maxVol)   # Convert from percent
        if vol < 10:
            vol = '0' + str(vol)
        url = baseUrl + 'formiPhoneAppDirect.xml?MV' + str(vol)
    if func == 'favorite':
        url = baseUrl + 'formiPhoneAppFavorite_Call.xml?' + command
    if url is not None:
        if (debug):
            log('Queuing ' + url)
        cmd_queue.append(url)

##
##      MQTT Callbacks
##

def mqttConnected(client, userdata, flags, rc):
    log('Connected to MQTT server ' + mqttServer)
    client.subscribe(mqttTopic + '#')

def mqttReceived(client, userdata, msg):
    message = msg.payload.decode('utf-8')
    log('MQTT message received: ' + msg.topic + ' ' + message)
    topic = msg.topic.split('/')[2]
    if topic in currentStatus:
        if currentStatus[topic] != message.upper():   
            hifiSend(topic, message.upper())
        else:
            if (debug):
                log('Ignoring MQTT message - no status change')
    else:
        log('Command received for unknown topic ' + topic)

##
##      Main
##

if __name__ == "__main__":
    mClient = mqttSub.Client('mqtt_hifi')
    mClient.on_connect = mqttConnected
    mClient.on_message = mqttReceived

    try:
        mClient.connect(mqttServer, 1883)
    except Exception as ex:
        log('Couldnt connect to MQTT server ' + mqttServer)
        sys.exit(1)

    hifiSync()
    mClient.loop_forever()


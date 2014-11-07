canary_app
==========

Takes values of temperature, humidity, luminancy and binary_sensor (PIR) and sends them to a remote client. Accepts timed on/off commands from the client. All messages are acknowledged in both directions and values are resent if there has not been an acknowledgement within a certain time.

Message formats are as follows:

Messages from the app:

    {
        "source": "string: Bridge ID/App ID",
        "destination": "string: Client ID",
        "body": {)
    }

An example of a source is BID254/AID11, which is app ID 11 on bridge ID 254. App IDs are always the same for a particular app.

An example of a client ID is CID5. 

Messages are routed by the ContinuumBridge bridge controller between the bridges and the client and the client and the bridges.

The body is as follows:

    {
        "s": <integer: sequence number>,
        "d" [
                {
                    "i": "string: device ID",
                    "c": "string: characteristic",
                    "v": "value",
                    "t": "integer: timestamp
                }
            ]
    }

The keys have the following meanings:

s  A sequence number that is incremented each time a message is sent. It is used to acknowledge the message.
d  An array of data. It may contain one or more elements.
i  The ID of the device that the data is from.
c  The characteristic, defined as follows:
   t  Temperature in degrees Celcius.
   h  Humidity in percent.
   l  Luminance n Lux.
   bn Binary sensor: 0 or 1. 0 is off and 1 is on.
   bt Battery status, percent.
   c  Connected: 0 or 1 to indicate whether the device is connected.
v  The value of the characteristic. 
t  Timestamp in seconds (Epoch time).

For devices that have more than one binary sensor (switch), the sensors are labelled b0 to bn-1, where n is the number of sensors.

Messages that originate from the client:

    {
        "source": "string: Client ID",
        "destination": "string: Bridge ID/Client ID",
        "body": {)
    }

The IDs are as defined above.

The body can be one of the following:



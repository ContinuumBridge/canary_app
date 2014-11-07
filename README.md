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

The body is as described below:

    {
        "s": <integer: sequence number>,
        "d" [
                {
                    "i": "string: device ID",
                    "c": "string: characteristic",
                    "v": "value",
                    "t": <integer: time>
                }
            ]
    } 

The difference between this and the message from the app is that the time is not a timestamp that indicates when the message was sent; it is a time that indicates when the app should action the message. The device ID is the ID of the device whose characteristic should be changed and the value is the value it shouild be changed to at time t. To turn on a heater controller called "control":

    {
        "s": 11,
        "d" [
                {
                    "i": "control",
                    "c": "s"",
                    "v": 1,
                    "t": 1415402453
                }
            ]
    } 
    
A mechanism is provided to acknowledge messages going in both directions. The header is as previously described and the body is as follows:

    {
        "a": <interger, acknowldge number>
    } 

The acknowledge field may also be included with another message, at the same level as the sequence number.

The sequence/acknowldge protocol works in a similar manner to TCP. An acknowledge number of N indicates that the next message that the receiver expects to receive is message N. Here is an example:

    AID -> CID  s=0     App sends first message
    AID -> CID  s=1     App sends second message
    CID -> AID  a=2     Client indicates it has received both messages

If the sender infers that a message has not been received, it should send it again. The app will keep data for a maximum of six hours before discarding it. In addition, the app does not attempt to send messages if it has been notified by the bridge manager that the connection is down. 

If either side sends a message with a sequence number of 0, any stored data will be discarded and the process restarted.


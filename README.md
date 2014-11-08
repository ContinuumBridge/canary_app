canary_app
==========

Takes values of temperature, humidity, luminancy and binary_sensor (PIR) and sends them to a remote client. Accepts timed on/off commands from the client. All messages are acknowledged in both directions and values are resent if there has not been an acknowledgement within a certain time.

Message formats are as follows:

Messages from the app:

    {
        "source": "string: Bridge ID/App ID",
        "destination": "string: Client ID",
        "body": {}
    }

An example of a source is BID254/AID11, which is app ID 11 on bridge ID 254. App IDs are always the same for a particular app.

An example of a client ID is CID5. 

Messages are routed by the ContinuumBridge bridge controller between the bridges and the client and the client and the bridges.

The body is as follows:

    {
        "n": <integer: sequence number>,
        "a": <integer: acknowledge number (optional)>,
        "d":
            [
                {
                    "i": "string: device ID",
                    <c>: <v>,
                    "s": <integer: timestamp>
                }
            ]
    }

The keys have the following meanings:

    n   Sequence number, described below.
    a   Acknowldge number, described below.
    i   The ID of the device that the data is from.
    c   The characteristic, defined as follows:
            t  Temperature in degrees Celcius.
            h  Humidity in percent.
            l  Luminance n Lux.
            bn Binary sensor: 0 or 1. 0 is off and 1 is on.
            bt Battery status, percent.
            c  Connected: 0 or 1 to indicate whether the device is connected.
    v  The value of the characteristic. 
    s  Timestamp in seconds (Epoch time).
    
The message body array may contain one or more samples. Note that the all fields in the body except the sequence number field are optional and upon connection or reconnection the app will send a message to the client that only contains the sequence number in the body. Once the client has acknowledged this, the app will then be able to send samples.

For devices that have more than one binary sensor (switch), the sensors are labelled b0 to bn-1, where n is the number of sensors.

Here is an example of the body of a message from an app. 

* The sequence number is 117. 
* There is no acknowledgement of any messages from the client. 
* It contains data from a device called "Sensor": 
    * a temperature reading of 18.5 deg C,
    * a humidity of 59.5%.
* The time at which the sensor readings were taken is 1415203274.

    {
        "n": 117,
        "d":
            [
                {
                    "i": "Sensor",
                    "t": 18.5,
                    "h": 59.5,
                    "s": 1415203274
                }
            ]
    }

Messages that originate from the client:

    {
        "source": "string: Client ID",
        "destination": "string: Bridge ID/Client ID",
        "body": {}
    }

The IDs are as defined above.

The body is as described below:

    {
        "n": <integer: sequence number>,
        "a": <integer: acknowledge number (optional)>,
        "d":
            [
                {
                    "i": "string: device ID",
                    <c>: <v>,
                    "at":<integer: time at which to action the value>
                }
            ]
    }

The device ID is the ID of the device whose characteristic should be changed and the value is the value it shouild be changed to at time "at". The following message body turns on a device called "Controller" at time 1415403000 and turns it off again at time 1415404000. The sequence number is 19 and the message also contains an acknowledgement, a (see below):

    {
        "n": 19,
        "a": 118,
        "d":
            [
                {
                    "i": "Controller",
                    "s": 1,
                    "at": 1415403000
                },
                {
                    "i": "Controller",
                    "s": 0,
                    "at": 1415404000
                }            
            ]
    }
    
A mechanism is provided to acknowledge messages going in either directions. Each time a message is sent, it contains a sequence number that is incremented by 1. An acknowledge message may then be sent back.

    {
        "source": "string",
        "destination": "string",
        "body": 
            {
                "s": <integer: sequence number>,
                "a": <integer: acknowledge number>
            }
    }

The acknowledge field may also be included with another message, as described above.

The acknowledge number indicates the next sequence number that the receiver is expecting. Eg:

    AID -> CID  s=0     App sends first message
    AID -> CID  s=1     App sends second message
    CID -> AID  a=2     Client indicates it has received both messages

If the sender infers that a message has not been received, it should send it again. The app will keep data for a maximum of six hours before discarding it. The app does not attempt to send messages if it has been notified by the bridge manager that the connection is down. 

If either side sends a message with a sequence number of 0, any stored data will be discarded and the process restarted.


import paho.mqtt.client as mqtt
from hardware import Room, MODE_OUT, MODE_IN
try:
    from sense_hat import SenseHat
except:
    from sense_emu.sense_hat import SenseHat
callbacks = {}
PREFIX = "room/"


def on_connect(mqtt_client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    for topic in callbacks.keys():
        print("subscribing to", PREFIX + "commands/" + topic)
        mqtt_client.subscribe(PREFIX + "commands/" + topic)


def on_message(mqtt_client, userdata, msg):
    print("recieved :", msg.payload, "in", msg.topic)
    if msg.topic.split('/')[-2] == "commands":
        if msg.topic.split('/')[-1] in callbacks.keys():
            callbacks[msg.topic.split('/')[-1]](msg.payload)


def send_mqtt(client, name, value):
    print("sending ", value, "in :", name)
    client.publish(name, payload=value, qos=0, retain=False)


if __name__ == "__main__":
    room = Room(SenseHat())
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    for mqtt_obj in room.mqtt_objects:
        if mqtt_obj.rw & MODE_OUT:
            print("binding ", PREFIX + mqtt_obj.name)
            mqtt_obj.sender = lambda name, value: send_mqtt(client, PREFIX + name, value)
        if mqtt_obj.rw & MODE_IN:
            callbacks[mqtt_obj.name] = mqtt_obj.set
    # client.username_pw_set("test", password="test")
    print("connecting..")
    client.connect_async("192.168.1.151", 1883, 60)
    client.loop_start()
    input()
    client.loop_stop(force=False)


try:
    from sense_hat import SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED
except:
    try:
        from sense_emu.sense_hat import SenseHat
        from sense_emu.stick import ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED
        print("No sense hat library, using the emulator")
    except:
        print("No sense hat library found, if you are using the emulator, please see README")
        exit()
import time
from threading import Thread, Event

LUMINOSITY_TARGET = 170

LUMINOSITY_STEPS = 15

MODE_OUT = 0b10
MODE_IN = 0b01


class MQTTComm:
    def __init__(self, target_object, name, mode=0):
        self.target = target_object
        self.name = name
        self.rw = mode
        self.sender = lambda n, x: print("unconfigured ", n, ": ", x)
        if mode & MODE_IN:
            self.set = lambda x: self.target(x)
        else:
            self.set = lambda a: None
        self.get = self.target
        self.notify_thread = None
        self.thd_exit = Event()

    def notify(self):
        self.sender(self.name, self.get())

    def notify_next(self, delay):
        while not self.thd_exit.is_set():
            self.notify()
            self.thd_exit.wait(delay)

    def set_periodic(self, delay):
        if not (self.rw & MODE_OUT):
            raise Exception("Non output variable cannot be periodic")
        self.notify_thread = Thread(target=self.notify_next, args=(delay,))
        self.notify_thread.start()
        return self

    def __del__(self):
        self.thd_exit.set()
        self.notify_thread.join()


class Store:

    def __init__(self, pixels: list[tuple[int, int]], sense: SenseHat):
        self.pixels = pixels
        self.sense = sense
        self.opening = 0

    def get_opening(self):
        return self.opening

    def set_opening(self, in_value):
        value = int(in_value)
        for (x, y) in self.pixels:
            self.sense.set_pixel(x, y, list(map(lambda i: i // 255, [value * 0xFF, value * 0xD9, value * 0x66])))
        self.opening = value


class Light:

    def __init__(self, pixels: list[tuple[int, int]], sense: SenseHat):
        self.pixels = pixels
        self.sense = sense
        self.intensity = 0

    def get_intensity(self):
        return self.intensity

    def set_intensity(self, value: int):
        for (x, y) in self.pixels:
            self.sense.set_pixel(x, y, [value] * 3)
        self.intensity = value


class Projector:
    def __init__(self, pixels: list[tuple[int, int]], sense: SenseHat):
        self.sense = sense
        self.pixels = pixels
        self.state = False
        self.sense.stick.direction_middle = self.toggle_proj
        self.mqtt_vars = [
            MQTTComm(self.get_activity, "projector_activity", MODE_OUT)
        ]

    def get_activity(self):
        return int(self.state)

    def toggle_proj(self, event):
        if event.action != ACTION_RELEASED:
            self.state ^= True
            self.mqtt_vars[0].notify()
            for (x, y) in self.pixels:
                self.sense.set_pixel(x, y, [self.state * 255] * 3)


class TempHumiditySensor:
    def __init__(self, sense: SenseHat):
        self.sense = sense
        self.mqtt_vars = [
            MQTTComm(self.get_temperature, "temperature", MODE_OUT).set_periodic(0.5 * 60),
            MQTTComm(self.get_humidity, "humidity", MODE_OUT).set_periodic(0.5 * 60)
        ]

    def get_temperature(self):
        return round(self.sense.get_temperature(), 2)

    def get_humidity(self):
        return round(self.sense.get_humidity(), 2)


class LightSimSensor:

    def __init__(self, sense: SenseHat):
        self.sense = sense
        self.luminosity_level = 0
        self.sense.stick.direction_up = self.augment_luminosity
        self.sense.stick.direction_down = self.lower_luminosity
        self.mqtt_vars = [
            MQTTComm(self.get_luminosity, "luminosity", MODE_OUT).set_periodic(1)
        ]

    def get_luminosity(self):
        return self.luminosity_level * 255 // LUMINOSITY_STEPS

    def aff_luminosity(self):
        lu = self.get_luminosity()
        self.sense.set_pixel(7, 7, [lu] * 3)

    def augment_luminosity(self, event):
        if event.action != ACTION_RELEASED:
            if self.luminosity_level < LUMINOSITY_STEPS:
                self.luminosity_level += 1
                self.aff_luminosity()

    def lower_luminosity(self, event):
        if event.action != ACTION_RELEASED:
            if self.luminosity_level > 0:
                self.luminosity_level -= 1
                self.aff_luminosity()


class StoreController:
    class StoreZone:
        def __init__(self, liste, default=0):
            self.stores = liste
            self.value = default

        def set_opening(self, value=None):
            if value is not None:
                self.value = int(value)
                for store in self.stores:
                    store.set_opening(self.value)
            else:
                return self.value

    def __init__(self, room_stores: list[Store], board_stores: list[Store]):
        self.room = self.StoreZone(room_stores)
        self.board = self.StoreZone(board_stores)
        self.mqtt_vars = [
            MQTTComm(self.room.set_opening, "room_store_opening", MODE_IN | MODE_OUT),
            MQTTComm(self.board.set_opening, "board_store_opening", MODE_IN | MODE_OUT),
            MQTTComm(self.set_opening, "global_store_opening", MODE_IN)
        ]

    def set_opening(self, value: int):
        self.room.set_opening(value)
        self.board.set_opening(value)


class LightController:
    class LightZone:
        def __init__(self, liste, default=0):
            self.lights = liste
            self.value = default

        def set_intensity(self, value=None):
            if value is not None:
                self.value = int(value)
                for light in self.lights:
                    light.set_intensity(self.value)
            else:
                return self.value

    def __init__(self, room_lights: list[Light], board_lights: list[Light]):
        self.room = self.LightZone(room_lights)
        self.board = self.LightZone(board_lights)
        self.mqtt_vars = [
            MQTTComm(self.room.set_intensity, "room_light_intensity", MODE_IN | MODE_OUT),
            MQTTComm(self.board.set_intensity, "board_light_intensity", MODE_IN | MODE_OUT),
            MQTTComm(self.set_intensity, "global_light_intensity", MODE_IN)
        ]

    def set_intensity(self, value: int):
        self.room.set_intensity(value)
        self.board.set_intensity(value)


class Room:
    def __init__(self, sense_hat_device: SenseHat):
        room_stores = [Store([(0, i), (0, i + 1)], sense_hat_device) for i in range(3, 7, 3)]
        board_stores = [Store([(0, 0), (0, 1)], sense_hat_device)]
        self.store_controller = StoreController(room_stores, board_stores)
        light_room = [Light([(j, i)], sense_hat_device) for j in (2, 5) for i in range(4, 7, 2)]
        light_board = [Light([(2, 2)], sense_hat_device), Light([(5, 2)], sense_hat_device)]
        self.light_controller = LightController(light_room, light_board)
        self.proj = Projector([(i, 0) for i in range(2, 6)], sense_hat_device)
        self.t_s_sensor = TempHumiditySensor(sense_hat_device)
        self.luminosity_sim = LightSimSensor(sense_hat_device)
        self.mqtt_objects = self.store_controller.mqtt_vars + self.light_controller.mqtt_vars + self.proj.mqtt_vars + \
                            self.t_s_sensor.mqtt_vars + self.luminosity_sim.mqtt_vars


if __name__ == "__main__":
    room = Room(SenseHat())
    while 1:
        time.sleep(0.05)
        lux = room.luminosity_sim.get_luminosity()
        store_opening = (255 - lux) + (255 - LUMINOSITY_TARGET) if lux > LUMINOSITY_TARGET else 255
        light_intensity = LUMINOSITY_TARGET - lux if lux < LUMINOSITY_TARGET else 0
        if room.proj.get_activity():
            room.light_controller.board.set_intensity(0)
            room.light_controller.room.set_intensity(light_intensity)
            room.store_controller.board.set_opening(0)
            room.store_controller.room.set_opening(store_opening)
        else:
            room.light_controller.set_intensity(light_intensity)
            room.store_controller.set_opening(store_opening)

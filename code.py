import asyncio
from random import randint, uniform
import board
import time
import busio
import digitalio
import displayio
import terminalio
import sys
from adafruit_display_text import label
import adafruit_displayio_sh1107
import adafruit_aw9523
import adafruit_requests as requests
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_socket as esp_socket



def esp_reset():
    print("ESP Reset BEGIN")
    try:
        esp.reset()
    except RuntimeError as e:
        print("ESP Reset Error:", e)
    time.sleep(1)
    print("ESP Reset END")


def esp_status_text(num):
    stat = {
        0: "WL_IDLE_STATUS",
        1: "WL_NO_SSID_AVAIL",
        2: "WL_SCAN_COMPLETED",
        3: "WL_CONNECTED",
        4: "WL_CONNECT_FAILED",
        5: "WL_CONNECTION_LOST",
        6: "WL_DISCONNECTED",
        7: "WL_AP_LISTENING",
        8: "WL_AP_CONNECTED",
        9: "WL_AP_FAILED",
        10: "WL_NO_SHIELD",
    }
    if num in stat:
        return stat[num]
    else:
        return "WL_UNDEFINED"


def esp_connect():
    esp_status = 255
    try:
        esp_status = esp.status
    except RuntimeError as e:
        print("ESP Status Error: ", e)
    try:
        esp_is_connected = esp.is_connected
    except RuntimeError as e:
        print("ESP Is Connected Error: ", e)
    # these should never disagree
    if esp_status == 3 and esp_is_connected:
        pass  # already connected
    else:
        try:
            print("ESP Connecting...")
            print(
                "ESP Status:      ",
                esp_status,
                esp_status_text(esp_status),
                "\n\tConnected?",
                esp_is_connected,
            )
            # "Will retry up to 10 times and return on success
            # or raise an exception on failure"
            # [1 second between each retry]
            esp.connect_AP("46C992", "meaty6250anne25bid")
            esp_status = esp.status
            esp_is_connected = esp.is_connected
            print(
                "ESP Status:      ",
                esp_status,
                esp_status_text(esp_status),
                "\n\tConnected?",
                esp_is_connected,
            )
        except RuntimeError as e:
            print("ESP Connection Error: ", e)
    return esp_status, esp_is_connected


def stop_wifi():
    """Stop WiFi on the ESP32.
    The `busio.SPI` object used is not deinitialized, since it may be in use for other devices.
    """
    print("Disconnecting WiFi...")
    try:
        esp.disconnect()
        print("WiFi disconnected")
    except RuntimeError as e:
        print("Unable to disconnect from WiFi: ", e)


displayio.release_displays()

i2c = board.I2C()  # uses board.SCL and board.SDA
# led_i2c = busio.I2C(board.SCL1, board.SDA1)
led_i2c = (
    board.STEMMA_I2C()
)  # For using the built-in STEMMA QT connector on a microcontroller
leddriver = adafruit_aw9523.AW9523(led_i2c)

# Set all pins to outputs and LED (const current) mode
leddriver.LED_modes = 0xFFFF
leddriver.directions = 0xFFFF

window_set = [12, 13, 14, 15]
window_set_1 = [11, 10, 9, 8]
always_on_set = [0, 1, 2]
always_on_set_maxes = [100, 15, 1]

# lights that are always on
for n in range(len(always_on_set)):
    leddriver.set_constant_current(always_on_set[n], always_on_set_maxes[n])


async def flicker(pin, min_curr, max_curr, interval):
    while True:
        rand_max_curr = randint(min_curr, max_curr)
        for i in range(min_curr, rand_max_curr):
            leddriver.set_constant_current(pin, i)  # aw9523 pin, current out of 255
            await asyncio.sleep(0.07)
        await asyncio.sleep(uniform(0.0, interval))


# Fades each light up and down one after the other
async def string_lights(interval, max_curr):
    while True:
        for i in range(len(window_set)):
            # fade up
            for j in range(max_curr):
                leddriver.set_constant_current(window_set[i], j)
                await asyncio.sleep(interval)
            for j in range(max_curr):
                # fade down
                x = max_curr - j
                leddriver.set_constant_current(window_set[i], x - 1)
                # leddriver.set_constant_current(window_set[i], max_curr-j)
                await asyncio.sleep(interval)


# Fades all lights on one after the other, then
# fades them off one after another
async def string_lights_1(interval, max_curr):
    while True:
        for i in range(len(window_set_1)):
            # fade up
            for j in range(max_curr):
                leddriver.set_constant_current(window_set_1[i], j)
                await asyncio.sleep(interval)
        for i in range(len(window_set_1)):
            # fade down
            for j in range(max_curr):
                x = max_curr - j
                leddriver.set_constant_current(window_set_1[i], x - 1)
                await asyncio.sleep(interval)


async def press_button_a(interval):
    pin_a = digitalio.DigitalInOut(board.D9)
    pin_a.direction = digitalio.Direction.INPUT
    pin_a.pull = digitalio.Pull.UP
    prev_state = pin_a.value
    text = "LED Controller\nWifi Connected:\n     " + str(esp.is_connected)
    x_coord = 23
    while True:
        cur_state = pin_a.value
        if cur_state != prev_state:
            if not cur_state:
                print("BTN is down")
                if text != "Disconnected Wifi":
                    stop_wifi()
                    if not esp.is_connected:
                        x_coord = 16
                        text = "Disconnected Wifi"
                    else:
                        x_coord = 0
                        text = "Unable to disconnect WiFi"
                else:
                    x_coord = 8
                    esp_connect()
                    if esp.is_connected:
                        text = "Connected to " + str(esp.ssid, "utf-8")
                    else:
                        text = "Unable to connect WiFi"
        text_area = label.Label(
            terminalio.FONT, text=text, color=0xFFFF00, x=x_coord, y=16
        )
        try:
            splash.pop(2)
        except IndexError:
            pass
        splash.append(text_area)
        prev_state = cur_state
        await asyncio.sleep(interval)


async def main():
    led3_task = asyncio.create_task(flicker(3, 1, 12, 0.7))
    led4_task = asyncio.create_task(flicker(4, 1, 7, 0.7))
    led5_task = asyncio.create_task(flicker(5, 1, 12, 0.7))
    led6_task = asyncio.create_task(flicker(6, 1, 10, 0.7))
    led7_task = asyncio.create_task(flicker(7, 1, 7, 0.7))
    leda_task = asyncio.create_task(string_lights(0.03, 30))
    ledb_task = asyncio.create_task(string_lights_1(0.03, 30))
    button_task = asyncio.create_task(press_button_a(0.1))
    await asyncio.gather(
        leda_task,
        ledb_task,
        led3_task,
        led4_task,
        led5_task,
        led6_task,
        led7_task,
        button_task
    )


spi = board.SPI()
esp32_cs = digitalio.DigitalInOut(board.D13)  # M4 Red LED
esp32_ready = digitalio.DigitalInOut(board.D11)
esp32_reset = digitalio.DigitalInOut(board.D12)
# esp32_gpio0 = DigitalInOut(board.D10)  # optional
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
esp_reset()
print("Checking ESP32...")
while True:
    try:
        esp_firmware_version = esp.firmware_version
        espfw = ""
        for _ in esp_firmware_version:
            if _ != 0:
                espfw += "{:c}".format(_)
        print("ESP Firmware:    ", espfw)
        sys.stdout.write("ESP MAC address ")
        cnt = 0
        for i in esp.MAC_address:
            if cnt == 5:
                sys.stdout.write("%02x" % (i) + "\n")
            else:
                sys.stdout.write("%02x:" % (i))
            cnt += 1
        esp_status = esp.status
        esp_is_connected = esp.is_connected
        print(
            "ESP Status:      ",
            esp_status,
            esp_status_text(esp_status),
            "\n\tConnected?",
            esp_is_connected,
        )
        break
    except RuntimeError as e:
        print("ESP Access Error:", e)
        esp_reset()
# don't proceed w/o a Wi-Fi connection
while True:
    try:
        if esp_connect() == (3, True):
            print("RSSI:   ", esp.rssi)
            print("SSID:    ", str(esp.ssid, "utf-8"))
            print(
                "BSSID:    {5:02X}:{4:02X}:{3:02X}:{2:02X}:{1:02X}:{0:02X}".format(
                    *esp.bssid
                )
            )
            print("IP:      ", esp.pretty_ip(esp.ip_address))
            print(
                "Netmask:  %d.%d.%d.%d"
                % (
                    esp.network_data["netmask"][0],
                    esp.network_data["netmask"][1],
                    esp.network_data["netmask"][2],
                    esp.network_data["netmask"][3],
                )
            )
            print(
                "Gateway:  %d.%d.%d.%d"
                % (
                    esp.network_data["gateway"][0],
                    esp.network_data["gateway"][1],
                    esp.network_data["gateway"][2],
                    esp.network_data["gateway"][3],
                )
            )
            print("LAN ping: %dms" % esp.ping(esp.network_data["gateway"]))
            print("WAN ping: %dms" % esp.ping("adafruit.com"))
            break
    except RuntimeError as e:
        print("ESP Wi-Fi Error:", e)
        esp_reset()




display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)

# SH1107 is vertically oriented 64x128
WIDTH = 128
HEIGHT = 64
BORDER = 2

display = adafruit_displayio_sh1107.SH1107(
    display_bus, width=WIDTH, height=HEIGHT, rotation=0
)

# Make the display context
splash = displayio.Group()
display.root_group = splash

color_bitmap = displayio.Bitmap(WIDTH, HEIGHT, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0xFFFFFF  # White

bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
splash.append(bg_sprite)

# Draw a smaller inner rectangle
inner_bitmap = displayio.Bitmap(WIDTH - BORDER * 2, HEIGHT - BORDER * 2, 1)
inner_palette = displayio.Palette(1)
inner_palette[0] = 0x000000  # Black
inner_sprite = displayio.TileGrid(
    inner_bitmap, pixel_shader=inner_palette, x=BORDER, y=BORDER
)
splash.append(inner_sprite)

# Draw a label
# text_area = label.Label(terminalio.FONT, text=text, color=0xFFFF00, x=28, y=15)
# splash.append(text_area)

# spi = board.SPI()

# button = digitalio.DigitalInOut(board.D9)
# button.switch_to_input(pull=digitalio.Pull.DOWN)
# text_area = label.Label(terminalio.FONT, text="", color=0xFFFF00, x=28, y=15)
# splash.append(text_area)


while True:
    asyncio.run(main())
    pass

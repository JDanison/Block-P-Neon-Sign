"""
    Filename: goldshimmer.py
    Filelocation:
        On Pi: /home/pi/Documents/ledDev/scripts
        On Git: Software --> LED Light Testing
    Author: John Danison
    Created Date: 12/18/2024
    
    Last Updated: 12/18/2024

    Description:
        This file contains the code for controlling the WS281x LED strips to be a shimmering gold. This is the desired set function that the wall mount will be.

    Physical Setup:
        GPIO 2: 5V
        GPIO 4: GND
        GPIO 18: Data Pin for LED Strip
"""

import time
from rpi_ws281x import PixelStrip, Color

# LED strip configuration:
LED_COUNT = 10        # Number of LED pixels on the strip
LED_PIN = 18          # GPIO pin connected to the LED strip (must support PWM, GPIO18)
LED_FREQ_HZ = 800000  # LED signal frequency (usually 800kHz for WS2812)
LED_DMA = 10          # DMA channel to use for generating signals
LED_BRIGHTNESS = 255  # Brightness (0-255)
LED_INVERT = False    # Invert signal (useful when using level shifters)
LED_CHANNEL = 0       # PWM channel

# Initialize the LED strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Function: Turn off all LEDs
def clear_strip():
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

# Function: Set all LEDs to one color
def solid_color(color, wait_ms=50):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    strip.show()
    time.sleep(wait_ms / 1000.0)

# Function: Rainbow color sequence
def rainbow(wait_ms=20, iterations=1):
    for j in range(256 * iterations):
        for i in range(strip.numPixels()):
            pixel_index = (i + j) & 255
            strip.setPixelColor(i, wheel(pixel_index))
        strip.show()
        time.sleep(wait_ms / 1000.0)

# Helper function: Generate rainbow colors across 0-255
def wheel(pos):
    pos = 255 - pos
    if pos < 85:
        return Color(255 - pos * 3, 0, pos * 3)
    if pos < 170:
        pos -= 85
        return Color(0, pos * 3, 255 - pos * 3)
    pos -= 170
    return Color(pos * 3, 255 - pos * 3, 0)

# Function: LED Chase Effect
def chase(color, wait_ms=50):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)
        strip.setPixelColor(i, Color(0, 0, 0))  # Turn off after moving

# Main program
if __name__ == "__main__":
    try:
        print("Press Ctrl+C to stop the program.")
        
        while True:
            print("Solid Color: Red")
            solid_color(Color(255, 0, 0))  # Red
            time.sleep(1)

            print("Solid Color: Green")
            solid_color(Color(0, 255, 0))  # Green
            time.sleep(1)

            print("Solid Color: Blue")
            solid_color(Color(0, 0, 255))  # Blue
            time.sleep(1)

            print("Chasing effect...")
            chase(Color(255, 0, 0))  # Red chase

            print("Rainbow effect...")
            rainbow()

    except KeyboardInterrupt:
        print("\nExiting program and clearing LEDs.")
        clear_strip()
"""
    Filename: lightsequencetesting.py
    Filelocation:
        On Pi: /home/pi/Documents/ledDev/scripts
        On Git: Software --> LED Light Testing
    Author: John Danison
    Created Date: 12/17/2024
    
    Last Updated: 12/20/2024

    Description:
        This file will serve as developement into getting the raspberry pi to run the LED lights on the outside ring of the block P.
        This will contain a run through several different sequences such that I can monitor and adjust whatever I may need to.

    Physical Setup:
        Light Strip:
        GPIO 4: GND
        GPIO 18: Data Pin for LED Strip

        Light Strip Power:
        Red to +V on external supply
        Black to -V on external supply

        This is done because the Pi cannot supply enough power by itself to power all LEDs in strip.
"""

import random
import time
from rpi_ws281x import PixelStrip, Color

# LED strip configuration:
LED_COUNT = 100        # Number of LED pixels on the strip
LED_PIN = 18          # GPIO pin connected to the LED strip (must support PWM, GPIO18)
LED_FREQ_HZ = 800000  # LED signal frequency (usually 800kHz for WS2812)
LED_DMA = 10          # DMA channel to use for generating signals
LED_BRIGHTNESS = 150  # Brightness (0-255)
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

# Function: Gold shimmer effect
def gold_shimmer():
    # Parameters For Color Fade
    wait_ms = 250
    shimmer_count = 20
    fade_steps = 10
    
    #Gold Colors
    gold = Color(195, 65, 0)  # Full gold color
    dim_gold = Color(140, 40, 0)  # Dimmed gold color
    
    # Set the entire strip to gold
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, gold)
    strip.show()
    
    # Create shimmer effect
    for _ in range(shimmer_count):
        # Randomly select LEDs to shimmer
        twinkle_leds = random.sample(range(strip.numPixels()), k = strip.numPixels() // 3)
        
        # Fade to dimmed gold
        for step in range(1, fade_steps + 1):
            for i in twinkle_leds:
                # Interpolate between full gold and dimmed gold
                r = int(195 - step * (195 - 140) / fade_steps)
                g = int(65 - step * (65 - 40) / fade_steps)
                b = int(0)  # No blue component in gold
                strip.setPixelColor(i, Color(r, g, b))
            strip.show()
            time.sleep(wait_ms / (1000.0 * fade_steps))
        
        # Fade back to full gold
        for step in range(1, fade_steps + 1):
            for i in twinkle_leds:
                # Interpolate between dimmed gold and full gold
                r = int(160 + step * (195 - 160) / fade_steps)
                g = int(40 + step * (65 - 40) / fade_steps)
                b = int(0)  # No blue component in gold
                strip.setPixelColor(i, Color(r, g, b))
            strip.show()
            time.sleep(wait_ms / (1000.0 * fade_steps))

        
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
        
            print("Gold Shimmer Effect")
            gold_shimmer()

    except KeyboardInterrupt:
        print("\nExiting program and clearing LEDs.")
        clear_strip()
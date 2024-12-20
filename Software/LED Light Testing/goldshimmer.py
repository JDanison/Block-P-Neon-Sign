"""
    Filename: goldshimmer.py
    Filelocation:
        On Pi: /home/pi/Documents/ledDev/scripts
        On Git: Software --> LED Light Testing
    Author: John Danison
    Created Date: 12/18/2024
    
    Last Updated: 12/20/2024

    Description:
        This file contains the code for controlling the WS281x LED strips to be a shimmering gold. This is the desired set function that the wall mount will be.

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
LED_COUNT = 50        # Number of LED pixels on the strip
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
        
        #Loop Gold Shimmer
        while True:
            print("Gold Shimmer")
            gold_shimmer()
        
    except KeyboardInterrupt:
        print("\nExiting program and clearing LEDs.")
        clear_strip()
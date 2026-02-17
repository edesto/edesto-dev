# Sensor Debug Example

A temperature monitoring sketch that reads simulated sensor values and converts them.

## Expected Behavior
The sketch should print Celsius and Fahrenheit readings every 2 seconds.
The conversion formula is: F = (C * 9/5) + 32

## How to Validate
Run `python validate.py` after flashing. It reads serial output and checks that
the Fahrenheit values match the expected conversion from the Celsius values.

## Known Issue
Users report that Fahrenheit readings seem too low. The Celsius values look correct.

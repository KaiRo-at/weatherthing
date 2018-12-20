#!/usr/bin/env python3

# Weather station WebThing

from asyncio import sleep, CancelledError, get_event_loop
from webthing import (Action, Event, Property, MultipleThings, Thing, Value,
                      WebThingServer)
import requests
import re
import logging
import time
import uuid

DEBUG = False
UPDATE_THING_SECONDS = 3
WEATHER_CACHE_SECONDS = 10
WEATHER_STATION_API = "http://192.168.13.3/rrd/weather.te838.week.json"

class HumiditySensor(Thing):
    """A humidity sensor which updates its measurement every few seconds."""

    def __init__(self, location_name, data_prefix):
        self.location_name = location_name
        self.data_prefix = data_prefix
        Thing.__init__(self,
                       "%s Humidity Sensor" % self.location_name.title(),
                       ["MultiLevelSensor"],
                       "The humidity sensor in %s" % self.location_name)

        self.level = Value(0.0)
        self.add_property(
            Property(self,
                     "level",
                     self.level,
                     metadata={
                         "@type": "LevelProperty",
                         "title": "%s Humidity" % self.location_name.title(),
                         "type": "number",
                         "description": "The current %s humidity in %%" % self.location_name,
                         "minimum": 0,
                         "maximum": 100,
                         "unit": "percent",
                         "readOnly": True,
                     }))

        if DEBUG:
            logging.debug("starting the %s humidity sensor update looping task", self.location_name)
        self.sensor_update_task = \
            get_event_loop().create_task(self.update_level())

    async def update_level(self):
        try:
            while True:
                await sleep(UPDATE_THING_SECONDS)
                weathervalues = get_weather_values();
                new_level = weathervalues["%s_hygro" % self.data_prefix] if weathervalues else None
                if DEBUG:
                    logging.debug("setting new %s humidity level: %s", self.location_name, new_level)
                self.level.notify_of_external_update(new_level)
        except CancelledError:
            # We have no cleanup to do on cancellation so we can just halt the
            # propagation of the cancellation exception and let the method end.
            pass

    def cancel_update_level_task(self):
        self.sensor_update_task.cancel()
        get_event_loop().run_until_complete(self.sensor_update_task)


class PressureSensor(Thing):
    """A air pressure sensor which updates its measurement every few seconds."""

    def __init__(self, location_name, data_name):
        self.location_name = location_name
        self.data_name = data_name
        Thing.__init__(self,
                       "%s Barometer" % self.location_name.title(),
                       ["MultiLevelSensor"],
                       "The barometer (air pressure sensor) in %s" % self.location_name)

        self.level = Value(0.0)
        self.add_property(
            Property(self,
                     "level",
                     self.level,
                     metadata={
                         "@type": "LevelProperty",
                         "title": "%s Air Pressure" % self.location_name.title(),
                         "type": "number",
                         "description": "The current %s air pressure in hPa/mbar" % self.location_name,
                         "minimum": 0,
                         "maximum": 10000,
                         "unit": "hPa",
                         "readOnly": True,
                     }))

        if DEBUG:
            logging.debug("starting the %s barometer update looping task", self.location_name)
        self.sensor_update_task = \
            get_event_loop().create_task(self.update_level())

    async def update_level(self):
        try:
            while True:
                await sleep(UPDATE_THING_SECONDS)
                weathervalues = get_weather_values();
                new_level = weathervalues[self.data_name] if weathervalues else None
                if DEBUG:
                    logging.debug("setting new %s air pressure level: %s", self.location_name, new_level)
                self.level.notify_of_external_update(new_level)
        except CancelledError:
            # We have no cleanup to do on cancellation so we can just halt the
            # propagation of the cancellation exception and let the method end.
            pass

    def cancel_update_level_task(self):
        self.sensor_update_task.cancel()
        get_event_loop().run_until_complete(self.sensor_update_task)


class TemperatureSensor(Thing):
    """A temperature sensor which updates its measurement every few seconds."""

    def __init__(self, location_name, data_prefix, has_humidity = False):
        self.location_name = location_name
        self.data_prefix = data_prefix
        self.has_humidity = has_humidity
        Thing.__init__(self,
                       "%s Temperature Sensor" % self.location_name.title(),
                       ["TemperatureSensor"],
                       "The temperature sensor in %s" % self.location_name)

        self.temperature = Value(0.0)
        self.add_property(
            Property(self,
                     "temperature",
                     self.temperature,
                     metadata={
                         "@type": "TemperatureProperty",
                         "title": "%s Temperature" % self.location_name.title(),
                         "type": "number",
                         "description": "The current %s temperature in °C" % self.location_name,
                         "unit": "degree celsius",
                         "readOnly": True,
                     }))

        if self.has_humidity:
            self.level = Value(0.0)
            self.add_property(
                Property(self,
                         "humidity",
                         self.level,
                         metadata={
                             "@type": "LevelProperty",
                             "title": "%s Humidity" % self.location_name.title(),
                             "type": "number",
                             "description": "The current %s humidity in %%" % self.location_name,
                             "minimum": 0,
                             "maximum": 100,
                             "unit": "percent",
                             "readOnly": True,
                         }))

        if DEBUG:
            logging.debug("starting the %s temperature sensor update looping task", self.location_name)
        self.sensor_update_task = \
            get_event_loop().create_task(self.update_level())

    async def update_level(self):
        try:
            while True:
                await sleep(UPDATE_THING_SECONDS)
                weathervalues = get_weather_values();
                new_temp = weathervalues["%s_temp" % self.data_prefix] if weathervalues else None
                if DEBUG:
                    logging.debug("setting new %s temperature: %s", self.location_name, new_temp)
                self.temperature.notify_of_external_update(new_temp)
                if self.has_humidity:
                    new_level = weathervalues["%s_hygro" % self.data_prefix] if weathervalues else None
                    if DEBUG:
                        logging.debug("setting new %s humidity level: %s", self.location_name, new_level)
                    self.level.notify_of_external_update(new_level)
        except CancelledError:
            # We have no cleanup to do on cancellation so we can just halt the
            # propagation of the cancellation exception and let the method end.
            pass

    def cancel_update_level_task(self):
        self.sensor_update_task.cancel()
        get_event_loop().run_until_complete(self.sensor_update_task)


# Get gas info from the weather station.
def get_weather_station_values(url):
    if DEBUG:
        logging.info("Get weather info from %s" % url)
    try:
        response = requests.get(url)
        if ('Content-Type' in response.headers
            and re.match(r'^application/json',
                         response.headers['Content-Type'])):
            # create a dict generated from the JSON response.
            wsdata = response.json()
            if response.status_code >= 400:
                # For error-ish codes, tell that they are from the weather station.
                wsdata["messagesource"] = "weatherstation"
            return wsdata, response.status_code
        else:
            return {"message": response.text,
                    "messagesource": "weatherstation"}, response.status_code
    except requests.ConnectionError as e:
        return {"message": str(e)}, 503
    except requests.RequestException as e:
        return {"message": str(e)}, 500


# Get values from weather station.
def get_weather_values():
    # Caching of actual values from weather station is done here.
    if (not hasattr(get_weather_values, "weather_station_values") or getattr(get_weather_values, "weather_station_values") is None
        or getattr(get_weather_values, "timestamp") < time.time() - WEATHER_CACHE_SECONDS):
        # Always set the timestamp so we do not have to test above if it's set,
        #  as it's only unset when token is also unset
        setattr(get_weather_values, "timestamp",  time.time())
        if not hasattr(get_weather_values, "weather_station_values"):
            setattr(get_weather_values, "weather_station_values", None)
        # Now, actually try to get the weather station values.
        weatherdata, weather_status_code = get_weather_station_values(WEATHER_STATION_API)
        if weather_status_code < 400:
            if DEBUG:
                logging.debug("Got HTTP status %s, save it." % weather_status_code)
            # Only cache new values if call was successful.
            setattr(get_weather_values, "weather_station_values", weatherdata)
        else:
            logging.error("Got HTTP status %s, weather data not usable." % weather_status_code)
    # Actually use cached values here.
    weathervalues = getattr(get_weather_values, "weather_station_values")
    latest_timestamp = None
    for timestamp in weathervalues:
        if not latest_timestamp or latest_timestamp < timestamp:
            latest_timestamp = timestamp
    return weathervalues[latest_timestamp]


def run_server():
    # Create a thing that represents a humidity sensor
    in_hygro = HumiditySensor("living room", "in")
    out_hygro = HumiditySensor("outside", "out")
    in_temp = TemperatureSensor("living room", "in", True)
    out_temp = TemperatureSensor("outside", "out", True)
    office_temp = TemperatureSensor("office", "office", True)
    kitchen_temp = TemperatureSensor("kitchen", "kitchen", True)
    bathroom_temp = TemperatureSensor("bathroom", "bathroom", True)
    bedroom_temp = TemperatureSensor("bedroom", "bedroom", True)
    baro = PressureSensor("outside", "baro")

    # If adding more than one thing, use MultipleThings() with a name.
    # In the single thing case, the thing's name will be broadcast.
    server = WebThingServer(
        MultipleThings(
            [in_hygro, out_hygro,
             in_temp, out_temp, office_temp, kitchen_temp,
             bathroom_temp, bedroom_temp,
             baro],
            "WeatherStation"),
        port=8888)
    try:
        logging.info("starting the server")
        server.start()
    except KeyboardInterrupt:
        logging.debug("canceling the sensor update looping task")
        in_hygro.cancel_update_level_task()
        out_hygro.cancel_update_level_task()
        in_temp.cancel_update_level_task()
        out_temp.cancel_update_level_task()
        office_temp.cancel_update_level_task()
        kitchen_temp.cancel_update_level_task()
        bathroom_temp.cancel_update_level_task()
        bedroom_temp.cancel_update_level_task()
        baro.cancel_update_level_task()
        logging.info("stopping the server")
        server.stop()
        logging.info("done")


if __name__ == '__main__':
    logging.basicConfig(
        level=10,
        format="%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
    )
    run_server()

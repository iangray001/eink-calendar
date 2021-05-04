
# eink Calendar and Weather Display

This project is built around the [7.5 inch HD panel from Waveshare](https://www.waveshare.com/wiki/7.5inch_HD_e-Paper_HAT_%28B%29). This has a resolution of 880x528. Other panels will require tweaks to the layout.


## API keys and credentials

When you first execute the script, it will create a `weather.json`. You will need to enter into this file the latitude and longitude of the forecast to display, and a [Met Office API key](https://www.metoffice.gov.uk/services/data/datapoint/api). 

To authorise the Google Calendar API, go to https://developers.google.com/calendar/quickstart/php and click on `Enable the Calendar API`. You can then download `credentials.json` and place it in the same folder as the main script. Execute `render.py` on your desktop/laptop, and it will load an authentication webpage, allowing you to complete authentication and generate a token, which the script will save as `token.json`. You can then copy all these files to the Raspberry Pi and it will execute headlessly.


##Options

For a full list of options run:

```
./render.py -h
```

The most important option is `-c` (or `--calendars`). This is how you tell the script which calendars from your Google Account to render, separated by commas. `primary` is a special calendar name understood by the Google Calendar API as the user's "main" calendar. For example:

```
./render.py -c primary,Work,Family
```

Calendar names with spaces are not currently supported.

One particularly useful option allows you to test the script locally by redirecting the output to image files rather than the eink. 

```
./render.py -o test -c Calendar1,Calendar2
```

This will create two files `test-b.png` and `test-r.png` which are the black and red channels respectively. 


The script supports caching to prevent unnecessary screen refreshes. If the `--cache <filename>` option is provided, then a file is created in the same directory as `render.py` which contains the events that were fetched in that run. Subsequent runs will only refresh the eink if the fetched events differ from the cache file contents. This allows you to have the script refresh much more frequently without causing distracting refreshes.


##Setting up the Pi

Almost any Raspberry Pi will work for this project, once [set up in as a headless device](https://aallan.medium.com/setting-up-a-headless-raspberry-pi-zero-3ded0b83f274). You will need to install the Python prerequisites:

```pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib pillow metoffer```

If metoffer is not installing from pip, you can find it at [github.com/sludgedesk/metoffer](github.com/sludgedesk/metoffer).

You will also need to install and set up the Waveshare drivers and Python libraries, details of which are available on the [Waveshare Wiki](https://www.waveshare.com/wiki/7.5inch_HD_e-Paper_HAT_%28B%29).

Once you have a headless Pi running that you can SSH to, clone this repository onto the Pi and set up a crontab to execute the refresh periodically. This example refreshes every five minutes using a cache file to ensure that the eink only refreshes when events change. Additionally on reboot the script is run without the cache to force a refresh. Edit your crontab with `crontab -e` and add the following, taking care to adjust the paths to point to the correct location.

```
*/5 * * * * /home/pi/eink/render.py -c primary --cache cachefile
@reboot /home/pi/eink/render.py -c primary
```

Finally, you might want to turn off the power and activity LEDs, which on most devices you can do by adding these lines to `/boot/config.txt`

```
dtparam=act_led_trigger=none
dtparam=act_led_activelow=off
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off
```

## Credits

The weather icons in this project are the [Meteocons project](https://www.alessioatzeni.com/meteocons) by Alessio Atzeni.

Fonts used:

 * [Louis George Cafe](https://www.dafont.com/louis-george-caf.font) by [Chen Yining](yiningchen23@gmail.com)
 * [Open Sans](https://fonts.google.com/specimen/Open+Sans) by Steve Matteson
 * [Pixellari](https://www.dafont.com/pixellari.font) by [Zacchary Dempsey-Plante](https://ztdp.ca/)










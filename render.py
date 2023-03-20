#!/usr/bin/env python3

import sys, os, time, optparse, platform, pprint, calendar, json, pickle
from datetime import datetime, timedelta
from PIL import Image,ImageDraw,ImageFont
import metoffer
from googleapiclient.discovery import build, Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

curdir = os.path.dirname(os.path.realpath(__file__))
fontdir = os.path.join(curdir, "fonts")

WeatherToMeteoGlyph = {
    "NA": ")", #Not available
    0: "C", #Clear night
    1: "B", #Sunny day
    2: "I", #Partly cloudy (night)
    3: "H", #Partly cloudy (day)
    4: ")", #Not used
    5: "M", #Mist
    6: "M", #Fog
    7: "N", #Cloudy
    8: "Y", #Overcast
    9: "Q", #Light rain shower (night)
    10: "Q", #Light rain shower (day)
    11: "Q", #Drizzle
    12: "Q", #Light rain
    13: "R", #Heavy rain shower (night)
    14: "R", #Heavy rain shower (day)
    15: "R", #Heavy rain
    16: "X", #Sleet shower (night)
    17: "X", #Sleet shower (day)
    18: "X", #Sleet
    19: "X", #Hail shower (night)
    20: "X", #Hail shower (day)
    21: "X", #Hail
    22: "U", #Light snow shower (night)
    23: "U", #Light snow shower (day)
    24: "U", #Light snow
    25: "W", #Heavy snow shower (night)
    26: "W", #Heavy snow shower (day)
    27: "W", #Heavy snow
    28: "P", #Thunder shower (night)
    29: "P", #Thunder shower (day)
    30: "P", #Thunder
}


def registerCalendarService():
    #From the Google Calendar API quickstart example
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = None
    if os.path.exists(os.path.join(curdir, 'token.json')):
        creds = Credentials.from_authorized_user_file(os.path.join(curdir, 'token.json'), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(os.path.join(curdir, 'credentials.json'), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(os.path.join(curdir, 'token.json'), 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)
    

def getIDsFromNames(calservice, names, printall):
    """
    names is a string of the names of calendars to show, delimited with comma
    i.e. "Main,Work"
    Result is an array of calendar IDs ready for the rest of the API
    """
    ids = []
    caldata = calservice.calendarList().list().execute()
    if printall:
        print("Calendar IDs in account:")
        for c in caldata['items']:
            print(c['id'])
        print("")
    cals = names.split(',')
    for c in cals:
        if c == "primary": #primary is a special ID understood by the API as the "main" calendar
            ids.append("primary")
            continue 
        for data in caldata.get('items', []):
            if data['summary'] == c:
                ids.append(data['id'])
                continue
    return ids


def getEvents(calservice, ids):
    """
    Returns a sorted list of events for the calendars in ids
    """
    now = datetime.utcnow().isoformat() + 'Z'
    events = []
    for id in ids:
        events_result = calservice.events().list(calendarId=id, timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime').execute()
        events.extend(events_result.get('items', []))

    rv = []
    for e in events:
        item = {
                "summary": e.get('summary', "No summary"),
                "location": e.get('location', "")
        }
        for se in ['start', 'end']:
            if 'date' in e[se]: item[se] = datetime.strptime(e[se]['date'], "%Y-%m-%d")
            if 'dateTime' in e[se]: item[se] = datetime.strptime(e[se]['dateTime'][:19], "%Y-%m-%dT%H:%M:%S")

        rv.append(item)

    rv = sorted(rv, key=lambda k: k['start']) 
    return rv


def eventsToDays(events, daystolook=7):
    '''
    Format an ordered list of events into a list of days, and the events that take place on that day.
    '''
    def suffix(d):
        return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

    def dateTimeAsPrettyString(dt):
        if dt.date() == datetime.now().date(): return "Today"
        if dt.date() == datetime.now().date() + timedelta(days=1): return "Tomorrow"
        return f"{datetime.strftime(dt.date(), '%A %-d')}{suffix(dt.date().day)} {datetime.strftime(dt.date(), '%B')}"

    days = []
    for e in events:
        if len(days) == 0 or e['start'].date() != days[-1]['date']:

            if (e['start'] - datetime.now()).days > daystolook: break

            days.append({
                'date': e['start'].date(),
                'datestring': dateTimeAsPrettyString(e['start']),
                'events': [e]
            })
        else:
            days[-1]['events'].append(e)

    return days


def allDay(start, end):
    '''
    There doesn't appear to be a flag in the Google event to denote an "all day" event, they simply start and end at midnight.
    '''
    return start.time().minute == 0 and start.time().hour == 0 and end.time().minute == 0 and end.time().hour == 0


def renderFrame(width, height, days, weather):
    '''
    Returns a pair of two PIL.Images of size width x height. The images are colour depth 1 (i.e. black and white). The first
    will be used as the "black" image and the second as the "red" image.
    '''    
    fonts = {
        'Meteocons': ImageFont.truetype(os.path.join(fontdir, 'meteocons.ttf'), 50), #70
        'DateSmall': ImageFont.truetype(os.path.join(fontdir, 'OpenSans-Regular.ttf'), 22),
        'DateBig': ImageFont.truetype(os.path.join(fontdir, 'OpenSans-Bold.ttf'), 100),
        'Pixellari16': ImageFont.truetype(os.path.join(fontdir, 'Pixellari.ttf'), 16),
        'MainText': ImageFont.truetype(os.path.join(fontdir, 'Louis George Cafe Bold.ttf'), 20),
    }

    bimage = Image.new('1', (width, height), 255)
    rimage = Image.new('1', (width, height), 255)
    id_b = ImageDraw.Draw(bimage)
    id_r = ImageDraw.Draw(rimage)

    bottomgutter = 400

    #Left border
    id_b.rectangle([(0, 0), (200, bottomgutter)], 0)

    #Date
    id_b.text((100, 40), datetime.strftime(datetime.now(), "%A"), font = fonts['DateSmall'], fill = 255, anchor="mt")
    id_b.text((100, 70), datetime.strftime(datetime.now(), "%-d"), font = fonts['DateBig'], fill = 255, anchor="mt")
    id_r.text((100, 70), datetime.strftime(datetime.now(), "%-d"), font = fonts['DateBig'], fill = 0, anchor="mt")
    id_b.text((100, 155), datetime.strftime(datetime.now(), "%B"), font = fonts['DateSmall'], fill = 255, anchor="mt")

    #Main text
    ypos = 20
    lineheight = 22
    for day in days:
        if ypos < (bottomgutter - lineheight):
            id_r.text((230, ypos), day['datestring'], font = fonts['MainText'], fill = 0)
            ypos = ypos + lineheight

            for e in day['events']:
                if ypos < (bottomgutter - lineheight):
                    if allDay(e['start'], e['end']):
                        text = f"  {e['summary']}"
                    else:
                        text = f"  {datetime.strftime(e['start'], '%-H:%M')} - {e['summary']}"
                    id_b.text((230, ypos), text, font = fonts['MainText'], fill = 0)
                    ypos = ypos + lineheight

            ypos = ypos + 6

    #Weather gutter
    id_b.rectangle([(0, bottomgutter-1), (width, bottomgutter+1)], 0)
    if weather != None:
        xpos = 50
        #Hourly forecasts, but we only want ones that are in the future
        filteredforecasts = [x for x in weather[0].data if x['timestamp'][0] > datetime.now()]

        for i in range(7):
            if i < len(filteredforecasts):
                timetext = filteredforecasts[i]['timestamp'][0].strftime("%H:%M")
                weathertext = WeatherToMeteoGlyph[filteredforecasts[i]['Weather Type'][0]]
                temptext = f"{filteredforecasts[i]['Feels Like Temperature'][0]}°C"

                id_r.text((xpos, bottomgutter+20), timetext, font = fonts['DateSmall'], fill = 0, anchor="mt")
                id_b.text((xpos, bottomgutter+65), weathertext, font = fonts['Meteocons'], fill = 0, anchor="mm")
                id_b.text((xpos, bottomgutter+100), temptext, font = fonts['DateSmall'], fill = 0, anchor="mt")
                xpos = xpos + 80

        #Daily forecasts
        id_b.rectangle([(xpos-21, bottomgutter), (xpos-19, height)], 0)
        xpos = xpos + 40
        for i in [2,4,6]: #Even results are 'day' forecasts, odd are 'night'
            timetext = weather[1].data[i]['timestamp'][0].strftime("%a")
            weathertext = WeatherToMeteoGlyph[weather[1].data[i]['Weather Type'][0]]
            temptext = f"{weather[1].data[i]['Feels Like Day Maximum Temperature'][0]}°"
            temptext2 = f"{weather[1].data[i+1]['Feels Like Night Minimum Temperature'][0]}°"

            id_r.text((xpos, bottomgutter+20), timetext, font = fonts['DateSmall'], fill = 0, anchor="mt")
            id_b.text((xpos, bottomgutter+65), weathertext, font = fonts['Meteocons'], fill = 0, anchor="mm")

            id_b.text((xpos-15, bottomgutter+100), temptext, font = fonts['DateSmall'], fill = 0, anchor="mt")
            id_b.text((xpos+15, bottomgutter+100), temptext2, font = fonts['Pixellari16'], fill = 0, anchor="mt")
 
            xpos = xpos + 80


    # Mini calendar view
    calx = 25
    caly = 270
    yinc = 20
    xinc = 25
    lettersofweek = [calendar.day_name[x][0] for x in range(7)]
    dayofweek, daysinmonth = calendar.monthrange(datetime.now().year, datetime.now().month)

    for i in range(len(lettersofweek)):
        id_b.text((calx + i*xinc, caly-1), lettersofweek[i], font = fonts['Pixellari16'], fill = 255, anchor="mt")

    id_b.rectangle([(calx-12, caly + yinc - 6), (calx+7*xinc-14, caly + yinc - 5)], 255)

    caly = caly + yinc
    for day in range(daysinmonth):
        id_b.text((calx + dayofweek * xinc, caly), f"{day+1}", font = fonts['Pixellari16'], fill = 255, anchor="mt")
        if day+1 == datetime.now().day:
            id_r.text((calx + dayofweek * xinc, caly), f"{day+1}", font = fonts['Pixellari16'], fill = 0, anchor="mt")
        dayofweek = dayofweek + 1
        if dayofweek == 7:
            dayofweek = 0
            caly = caly + yinc

    return (bimage, rimage)


def main():
    cmdparser = optparse.OptionParser()
    cmdparser.add_option("--noclear", action="store_true", default=False, help="Do not clear the eink before drawing.")
    cmdparser.add_option("--noweather", action="store_true", default=False, help="Do not draw the weather forecast.")
    cmdparser.add_option("-o", "--output", type="string", default="", help="Save the output to two files called output-b.png and output-r.png. Will not attempt to draw on eink.")
    cmdparser.add_option("-i", "--input", type="string", default="", help="Do not render a frame, draw the provided images to the eink. This option is the 'black' image. Use in conjunction with --redinput.")
    cmdparser.add_option("-r", "--redinput", type="string", default="", help="The 'red' image file for use with --input.")
    cmdparser.add_option("-c", "--calendars", type="string", default="primary", help="Calendar IDs to use, delimited by comma.")
    cmdparser.add_option("-v", "--verbose", action="store_true", default=False, help="Verbose mode.")
    cmdparser.add_option("--width", type="int", default=880, help="If not drawing to eink, output width of image.")
    cmdparser.add_option("--height", type="int", default=528, help="If not drawing to eink, output height of image.")
    cmdparser.add_option("-d", "--days", type="int", default=7, help="Number of days to look ahead for events.")
    cmdparser.add_option("--cache", type="string", help="Filename of cache file to save fetched events to. Will only redraw if the events have changed.")
    cmdparser.add_option("--cachehours", type="int", default=2, help="Number of hours that the cache remains valid for.")

    
    (options, _) = cmdparser.parse_args()

    if (options.redinput != "" and options.input == "") or (options.redinput == "" and options.input != ""):
        print("Options --input and --redinput must be used together.")
        sys.exit(1)

    if options.output == "":
        if platform.system() != "Linux":
            print("Cannot use the Waveshare libraries on a non-Linux platform. Use the --output option to output to an image file.")
            sys.exit(1)
        try:
            from waveshare_epd import epd7in5b_HD
        except ImportError:
            print("Could not find the waveshare_epd libraries. Download the Waveshare Python code from https://www.waveshare.com/wiki/7.5inch_HD_e-Paper_HAT_%28B%29 and ensure it is visible to Python.")
            sys.exit(1)
        epd = epd7in5b_HD.EPD()
        epd.init()
        options.width = epd.width
        options.height = epd.height

    redraw = True

    if options.input == "":
        calservice = registerCalendarService()
        ids = getIDsFromNames(calservice, options.calendars, options.verbose)
        events = getEvents(calservice, ids)
        days = eventsToDays(events, options.days)
    
        if not options.noweather:
            if os.path.exists(os.path.join(curdir, 'weather.json')):
                with open(os.path.join(curdir, 'weather.json')) as f:
                    data = json.load(f)
                if not "lat" in data and not "lon" in data and not "apikey" in data:
                    print("weather.json is in an incorrect format.")
                    sys.exit()
            else:
                weatherjson = '{\n\t"lat": "54.9755153",\n\t"lon": "-1.6222127",\n\t"apikey": "00000000-0000-0000-0000-000000000000"\n}'
                with open(os.path.join(curdir, 'weather.json'), 'a') as f:
                    f.write(weatherjson)
                print("weather.json created. Fill it in and retry.")
                sys.exit()

            mo = metoffer.MetOffer(data['apikey'])
            forecast = mo.nearest_loc_forecast(float(data['lat']), float(data['lon']), metoffer.THREE_HOURLY)
            dailyforecast = mo.nearest_loc_forecast(float(data['lat']), float(data['lon']), metoffer.DAILY)
            weather = (metoffer.Weather(forecast), metoffer.Weather(dailyforecast))

            if options.verbose: print(f"Weather forecast for {weather[0].name} fetched.")
        else:
            weather = None


        if options.cache != None:
            cachefile = os.path.join(curdir, options.cache)
            if os.path.exists(cachefile):
                try:
                    (cacheddays, cachedtime) = pickle.load(open(cachefile, "rb"))
                    if cacheddays == days and datetime.now() < cachedtime + timedelta(hours=options.cachehours):
                        #Nothing has changed
                        if options.verbose: print(f"Fetched data is the same as cached data.")
                        redraw = False
                except:
                    #Any errors handling the cache, just invalitate it
                    print("Error whilst reading cache: ", sys.exc_info()[0])
            #Else we will update the cache
            #We store the days dictionary and the current time in the cache, because the MetOffice objects are incomparable and this
            #is the easiest way to ensure that we update at least frequently enough to show the new forecast.
            pickle.dump((days, datetime.now()), open(cachefile, "wb"))

        if options.verbose:
            pprint.pprint(days)

        if redraw:
            if options.verbose: print("Drawing frame.")
            (bimage, rimage) = renderFrame(options.width, options.height, days, weather)
    else:
        bimage = Image.open(os.path.join(curdir, options.input))
        rimage = Image.open(os.path.join(curdir, options.redinput))

    if options.output == "":
        if redraw:
            if options.noclear == False:
                if options.verbose: print("Clearing eink.")
                epd.Clear()
                if options.verbose: print("eink cleared.")

            if options.verbose: print("Sending frame to eink.")

            epd.display(epd.getbuffer(bimage),epd.getbuffer(rimage)) 
            if options.verbose: print("eink done.")
            epd.sleep()
        else:
            if options.verbose: print("eink not updated because fetched data matches cache.")
    else:
        if redraw:
            bimage.save(options.output + "-b.png", format="png")
            rimage.save(options.output + "-r.png", format="png")
            if options.verbose: print(f"Rendered frame saved to {options.output}-b.png and {options.output}-r.png.")
        else:
            if options.verbose: print("Output files not updated because fetched data matches cache.")

if __name__ == "__main__":
    main()

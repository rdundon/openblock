#!/usr/bin/env python
# encoding: utf-8
#pylint: disable-msg=E1101
#pylint: disable-msg=W0142

"""
add_events.py

Created by Don Kukral <don_at_kukral_dot_org>

Downloads calendar entries from RSS feed at boston.com 
and updates the database
"""

import sys, feedparser, datetime
import logging

from django.contrib.gis.geos import Point
from ebpub.db.models import NewsItem, Schema

# Note there's an undocumented assumption in ebdata that we want to
# put unescape html before putting it in the db.  Maybe wouldn't have
# to do this if we used the scraper framework in ebdata?
from ebdata.retrieval.utils import convert_entities

logger = logging.getLogger()

def main():
    """ Download Calendar RSS feed and update database """
    logger.info("Starting add_events")
    url = """http://calendar.boston.com/search?acat=&cat=&commit=Search\
&new=n&rss=1&search=true&sort=0&srad=20&srss=50&ssrss=5&st=event\
&st_select=any&svt=text&swhat=&swhen=today&swhere=&trim=1"""
    schema = 'events'


    try:
        schema = Schema.objects.get(slug=schema)
    except Schema.DoesNotExist:
        logger.error("Schema (%s): DoesNotExist" % schema)
        sys.exit(1)

    feed = feedparser.parse(url)

    for entry in feed.entries:
        try:
            item = NewsItem.objects.get(title=entry.title,
                description=entry.description)
            status = "Updated"
        except NewsItem.DoesNotExist:
            item = NewsItem()
            status = "Added"

        try:
            item.location_name = entry.get('xcal_x-calconnect-street') or entry.get('x-calconnect-street')
            item.schema = schema
            item.title = convert_entities(entry.title)
            item.description = convert_entities(entry.description)
            item.url = entry.link
            item.item_date = datetime.datetime(*entry.updated_parsed[:6])
            item.pub_date = datetime.datetime(*entry.updated_parsed[:6])
            item.location = Point((float(entry['geo_long']),
                                   float(entry['geo_lat'])))
            if (item.location.x, item.location.y) == (0.0, 0.0):
                logger.warn("Skipping %r, bad location 0,0" % item.title)
                continue

            if not item.location_name:
                # Fall back to reverse-geocoding.
                from ebpub.geocoder import reverse
                try:
                    block, distance = reverse.reverse_geocode(item.location)
                    logger.info(" Reverse-geocoded point to %r" % block.pretty_name)
                    item.location_name = block.pretty_name
                except reverse.ReverseGeocodeError:
                    logger.debug(" Failed to reverse geocode %s for %r" % (item.location.wkt, item.title))
                    item.location_name = u''

            item.save()
            logger.info("%s: %s" % (status, item.title))
        except ValueError:
            logger.debug("unexpected error:", sys.exc_info()[1])
    logger.info("add_events finished")

if __name__ == '__main__':
    sys.exit(main())


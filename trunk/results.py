#!/usr/bin/env python

import os
import wsgiref.handlers
import logging as log
import urllib
from django.utils import simplejson as json
import cProfile, pstats, StringIO
from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template

import twitgraph_base_servlet
from classifier.classifier import BayesianClassifier

class ResultsHandler(twitgraph_base_servlet.BaseHandler):

  SEARCH_URL = 'http://search.twitter.com/search.json'

  def get(self):
    all_results = self.fetch_results(self.get_twitter_query())
    classified_results = self.classify(all_results)
    template_values = self.get_template_values();
    template_values['json_results'] = json.dumps(classified_results)
    path = os.path.join(os.path.dirname(__file__), 'results.json')
    self.response.out.write(template.render(path, template_values))

  def classify(self, results):
    """Classifies the results set by adding a "tag" attribute to each of the results.

    The same set of results are returned, with additional statistics and tagging.
    Each result gets one of the tags :), :( or :|
    And a stats section is added.

    @return An Object with two elements:
    {"results": [{"tag": "pos",
                  "iso_language_code": "en",
                  "text": "@chucklelate im not that excited about google voice. although it seems neat, i dont see myself using it.",
                  "created_at": "Sat, 14 Mar 2009 00:00:03 +0000",
                  "profile_image_url": "http:\/\/s3.amazonaws.com\/twitter_production\/profile_images\/80373954\/IMG_0008_normal.JPG",
                  "to_user": "chucklelate",
                  "source": "<a href="http:\/\/twitter.com\/">web<\/a>",
                  "from_user": "richeymanic",
                  "from_user_id": 5160745,
                  "to_user_id": 409063,
                  "id": 1324759664},...],
     "stats": {"pos": 50, "neg": 48, "neu": 102}}
    """
    c = BayesianClassifier()
    stats = {c.POSITIVE: 0, c.NEGATIVE: 0, c.NEUTRAL: 0}
    for result in results:
      tag = c.classify(result['text'])
      result['tag'] = tag
      stats[tag] = stats[tag] + 1

    classified = {"results": results, "stats": stats}

    return classified


  def fetch_results(self, query):
    """Fetches all search results from twitter for the given query.

    This method will call twitter API iteratively again and again until it exausts all resutls for that query.

    @return An array of results. Each result is a json object. Example:
      [{"iso_language_code": "en",
        "text": "@chucklelate im not that excited about google voice. although it seems neat, i dont see myself using it.",
        "created_at": "Sat, 14 Mar 2009 00:00:03 +0000",
        "profile_image_url": "http:\/\/s3.amazonaws.com\/twitter_production\/profile_images\/80373954\/IMG_0008_normal.JPG",
        "to_user": "chucklelate",
        "source": "<a href="http:\/\/twitter.com\/">web<\/a>",
        "from_user": "richeymanic",
        "from_user_id": 5160745,
        "to_user_id": 409063,
        "id": 1324759664},
       {...},...]
    """
    url = "%s?%s" % (self.SEARCH_URL, query)
    all_results = []
    while True:
      result = self.fetch_single_request(url)
      if not result:
        # Error
        log.error("Resutls empty, error")
        break
      all_results.extend(result.get('results'))
      if result.get('next_page'):
        url = "%s%s" % (self.SEARCH_URL, result.get('next_page'))
      elif result.get('max_id') == -1:
        # Error
        log.error("result.max_id == -1")
        break
      else:
        # That's OK, finished successfuly
        break
    return all_results

  def fetch_single_request(self, url):
    """Makes a single call to twitter and returns its results"""
    log.info("Sending request to %s", url)
    try:
      result = urlfetch.fetch(url)
      if result.status_code == 200:
        log.info("Response: %s...", (result.content)[0:10])
        return json.loads(result.content)
      else:
        log.error("Error from twitter: %s", result)
    except urlfetch.Error, e:
      log.error("Exception when contacting twitter %s", e)
    return None

  def get_twitter_query(self):
    query = {'q': ('%s since:%s until:%s' % (self.get_q(), self.get_start(), self.get_end())),
        'rpp': 100};
    return urllib.urlencode(query)

def real_main():
  application = webapp.WSGIApplication([('/results.json', ResultsHandler)],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)

def profile_main():
  # This is the main function for profiling
  # We've renamed our original main() above to real_main()
  prof = cProfile.Profile()
  prof = prof.runctx("real_main()", globals(), locals())
  stream = StringIO.StringIO()
  stats = pstats.Stats(prof, stream=stream)
  stats.sort_stats("time")  # Or cumulative
  stats.print_stats(5)  # 80 = how many to print
  # The rest is optional.
  # stats.print_callees()
  # stats.print_callers()
  log.info("Profile data:\n%s", stream.getvalue())

if __name__ == '__main__':
  profile_main()

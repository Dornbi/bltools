#!/usr/bin/python
# -*- coding: utf-8
#
# Copyright (c) 2014     , Frank Löffler
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Fetches shop prices for items from the Lego Bricks and Pieces site
"""

import json
import re
import sys
import urllib, urllib2, cookielib
import random
import json
import pickle

from HTMLParser import HTMLParser

BAPCACHEFILE = '.bltools-cache/bap_cache'

BAPKNOWN_UNKNOWN = {6092590: 88,}

class BaPResultHtmlParser(HTMLParser):
  def __init__(self, part_id):
    HTMLParser.__init__(self)
    self._state = 0
    self._result = []
    self._current_dict = {}
    self._part_id = part_id
  
  def handle_starttag(self, tag, attrs):
    attr_dict = dict(attrs)
    if self._state == 1 and tag == 'b':
      self._state += 1
    elif (self._state == 3 and tag == 'a' and
        attr_dict.setdefault('href', '').startswith('/catalogItemIn.asp?P=%s&colorID='%self._part_id)):
      m = re.match(r'/catalogItemIn.asp\?P=%s[^&]*&colorID=([0-9]+)&in=A'%self._part_id,
                   attr_dict.setdefault('href', ''))
      if m:
        self._current_dict['current_colorcode'] = m.group(1)
        self._state += 1
    elif (self._state == 11 and tag == 'b'):
      self._state += 1
    elif (self._state == 13 and tag == 'b'):
      self._state += 1

  def handle_data(self, data):
    if self._state == 0 and data == ' is the part and color combination code for this part in ':
      self._state += 1
    elif self._state == 0 and data == ' is the part and color combination code for:':
      self._current_dict['needs_refetch'] = True
      self._state = 11
    elif self._state == 2:
      self._current_dict['colorname'] = data
      self._state += 1
    elif self._state == 4:
      if (data == self._current_dict['colorname']):
        self._current_dict['colorcode'] = self._current_dict['current_colorcode']
        self._result.append(self._current_dict)
      self._state = 3
    elif self._state == 12:
      if not 'part_ids' in self._current_dict:
        self._current_dict['part_ids'] = {}
      self._current_dict['current_part_id'] = data
      self._state += 1
    elif self._state == 14:
      self._current_dict['part_ids'][self._current_dict['current_part_id']] = data
      self._state = 11

  def handle_endtag(self, tag):
    if self._state > 10 and tag == 'font':
      self._result.append(self._current_dict)
      self._state = 1

class BaPResultHtmlParserPartIDs(HTMLParser):
  def __init__(self):
    HTMLParser.__init__(self)
    self._state = 0
    self._result = None

  def handle_starttag(self, tag, attrs):
    attr_dict = dict(attrs)
    if self._state == 0 and tag == 'font':
      self._state += 1
    if self._state == 2 and tag == 'br':
      self._state += 1

  def handle_data(self, data):
    if self._state == 1 and data == 'Item No:':
      self._state += 1
    elif self._state == 3:
      self._result = data.replace(" or ",",").replace(" or ",",").split(",")
      self._state += 1


BaPinitialized = False
BaPopener      = None

# Small function to handle http errors in a consistent way
def BaPmyopen(opener, url, post=None, errstr=""):
  try:
    conn = opener.open(url, post)
  except Exception as e:
    print('Could not connect to Bricks and Pieces. Check your connection '+
          'and try again. (%s)' % errstr)
    print e
    sys.exit(1)
  return conn

def BaPGetCache():
  # Cache data
  try:
         BaPData = pickle.load(open(BAPCACHEFILE, 'rb'))
  except:
    BaPData = {'p':{}, 'e':{}, 'a':{}}
  return BaPData

""" Get element IDs from the BaP website that match a given part_id.
    This can be zero (not available/known), one or many IDs, because the
    part_id alone does not specify any color, so this function returns
    an array of the data of elements with a given part_id.
"""
def BaPFetchLegoInfo(opener, part_id):
  # See if data is already in cache
  BaPData = BaPGetCache()
  if (part_id in BaPData['p']):
    return BaPData['p'][part_id]

  # Lego does not handle part_ids that contain letters. These are used by BL to distinguish
  # between different types of the same design, but these "extensions" are not used by Lego.
  # So, in order to find something at BaP under the part_id, we have to remove everything
  # after, and including the first letter
  short_part_id = re.sub(r'[^0-9]+.*', '', part_id)
  conn = BaPmyopen(opener,
         r'https://service.lego.com/rpservice/rpsearch/getreleasedbricks?searchText=%s'%short_part_id,
         errstr='Brick fetching')
  rawdata = conn.read()
  try:
    data = json.JSONDecoder().decode(rawdata)
  except:
    print "Could not decode json data."
  # Cache data
  if (len(data['I']) > 0):
    BaPData['p'][part_id] = data['I']
    pickle.dump(BaPData, open(BAPCACHEFILE, 'wb'))
  return data['I']


# We have to have a session id and some cookie variables set to get to the
# prices. This isn't really logging in with any account, but technically
# it is the same
def BaPInit():
  global BaPinitialized, BaPopener
  if (BaPinitialized):
    return
  SL = r'https://service.lego.com'
  cj = cookielib.CookieJar()
  opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
  # Set some headers to make us not too obvious
  opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; Linux x86_64; rv:31.0)'),
                       ('Referer', 'https://service.lego.com/en-us/replacementparts/')]
  # First get most of the necessary cookies and headers to move on
  BaPmyopen(opener, SL+r'/en-us/replacementparts/#BasicInfo',
         errstr='BasicInfo')
  # Next set age and country, TODO: randomize age a bit
  BaPmyopen(opener, SL+r'/rpservice/rpaddress/setageandcountry?RPAge=33&RPCountry=US',
         errstr='age and country')
  BaPmyopen(opener, SL+r'/en-us/replacementparts/IssueType', {},
         errstr='IssueType')
  BaPmyopen(opener, SL+r'/rpservice/rpaddress/settype?RPType=3',
         errstr='SetType')
  BaPmyopen(opener, SL+r'/en-us/replacementparts//WhatStore',
         errstr='WhatStore')
  BaPopener = opener
  BaPinitialized = True


def BaPGetAlternate_PartIDs(part_id):
  global BaPopener
  BaPInit()
  BaPData = BaPGetCache()
  if part_id in BaPData['a']:
    return BaPData['a'][part_id]
  conn = BaPmyopen(BaPopener, 'http://www.bricklink.com/catalogItem.asp?P=%s' % part_id)
  html = conn.read()
  parser = BaPResultHtmlParserPartIDs()
  parser.feed(html)
  if parser._result:
    BaPData['a'][part_id] = parser._result
    pickle.dump(BaPData, open(BAPCACHEFILE, 'wb'))
  return parser._result

# Get a BL part id and color, and get the price information back from Bricks and Pieces
def BaPFetchShopInfo(part_id, part_color):
  global BaPopener
  BaPInit()
  # This gets us info about available pieces (in any color)
  part_info = None
  # Get element IDs from cache, if we can find them there
  BaPData = BaPGetCache()
  if part_id in BaPData['p']:
    sys.stdout.write(" cached ")
    sys.stdout.flush()
    part_info = BaPData['p'][part_id]
  # If we couldn't find them in the cache, fetch the info from the BaP website
  if (part_info == None):
    part_info = BaPFetchLegoInfo(BaPopener, part_id)
    BaPData = BaPGetCache()
  # We asked for a part id, but this does not specify the color. We need to get
  # all available element IDs (which encode also the color), and cross-check
  # with Bricklink if it is the one we are interested in. In other words, we need
  # to connect one of the element IDs to the BL color code we've been given.
  #print " BaP: ",len(part_info), "candidates found for %s (%d)" % (part_id, part_color)
  if (part_info == None or len(part_info) == 0):
    part_info = []
  found = False
  for part in part_info:
    element_id = part['ItemNo']
    design_id  = str(part['DesignId'])
    short_part_id = re.sub(r'[^0-9]+.*', '', part_id)
    if (design_id != short_part_id):
      # This can happen because some parts do have multiple part numbers that
      # are equivalent. We need to check if this is the case here.
      alternatives = BaPGetAlternate_PartIDs(part_id)
      if (not alternatives or not design_id in alternatives):
        print("Inconsistency in return from Lego: got different part/design id back: "+
              "%s!=%s, eid %s" %(
              design_id, part_id, element_id))
        #sys.exit(1)
    elif part['Price'] > 0:
      colorcode = -1
      if (element_id in BaPData['e']):
        colorcode = BaPData['e'][element_id]['color']
      else:
        BLurl = r'http://www.bricklink.com/catalogList.asp?q=%d'%element_id
        conn = BaPmyopen(BaPopener, BLurl)
        html = conn.read()
        parser = BaPResultHtmlParser(part_id)
        parser.feed(html)
        if (len(parser._result) == 0):
          print "Could not find result on BL: ", BLurl
          if element_id in BAPKNOWN_UNKNOWN:
            print " ... but found hardcoded in blutils."
            colorcode = BAPKNOWN_UNKNOWN[element_id]
          else:
            print parser._result
            print part
            print "BL part_id :", part_id
            sys.exit(1)
        if (colorcode < 0):
          if 'needs_refetch' in parser._result[0]:
            if not part_id in parser._result[0]['part_ids']:
              print part, " not found on BL: ", BLurl
              print parser._result[0]
              sys.exit(1)
            colorcode = part_color # THIS IS AN ASSUMPTION
          else:
            colorcode = int(parser._result[0]['colorcode'])
        if not element_id in BaPData['e']:
          BaPData['e'][element_id] = {'design_id': design_id, 'color': colorcode}
          pickle.dump(BaPData, open(BAPCACHEFILE, 'wb'))
      if (colorcode == part_color):
        found = part
        break
  if found:
    #print "Found: Part %s in color %d (Element ID %s): %s %s" % (
    #      part_id, part_color, element_id, found['Price'], found['CId'])
    return {'quantity'  : 200,
            'unit_price': found['Price'],
            'min_buy'   : 0.0,
            'location'  : 'USA',
            'condition' : 'N',
            'shop_name' : 'Lego Bricks and Pieces',
            'lotpic'    : 'https://a248.e.akamai.net/cache.lego.com'+found['Asset'],
           }
  return None

#print BaPFetchShopInfo('61485', 86)

#!/usr/bin/python
# -*- coding: utf-8
#
# Copyright (c) 2014-2014, Frank Löffler
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
Login to Bricklink - utility for operations that need a signed-in user
"""

import sys, urllib, urllib2, cookielib

from gflags import FLAGS

"""
Login to Bricklink, and return a urllib2.build_opener() to further use
"""
def BricklinkLogin():
  # We have to use cookies to stay logged in
  cj = cookielib.CookieJar()
  opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
  if (FLAGS.user == None or FLAGS.passwd == None):
    print 'You have to specify user name and password for this operation.'
    sys.exit(1);
  url_params = urllib.urlencode({
      'a': 'a',
      'logFrmFlag' : 'Y',
      'frmUsername' : FLAGS.user,
      'frmPassword' : FLAGS.passwd,
    })
  url = 'https://www.bricklink.com/login.asp?logInTo=&logFolder=p&logSub=w'
  try:
    conn = opener.open(url, url_params)
  except:
    print 'Could not connect to BrickLink. Check your connection and try again.'
    sys.exit(1)
  html = conn.read()
  # TODO: check that this actually worked
  # now return the opener, to be used for subsequent requests
  return opener


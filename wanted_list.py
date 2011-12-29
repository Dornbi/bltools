#!/usr/bin/python
#
# Copyright (c) 2011-2012, Peter Dornbach.
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
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
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
Outputs a wanted list XML file.
"""

def OutputWantedList(f, parts_dict, allow_used=[], wanted_list_id=None):
  f.write('<INVENTORY>\n')
  for key in sorted(parts_dict):
    f.write(' <ITEM>\n')
    f.write('  <ITEMTYPE>P</ITEMTYPE>\n')
    f.write('  <ITEMID>%s</ITEMID>\n' % key.split('-')[0])
    f.write('  <COLOR>%s</COLOR>\n' % key.split('-')[1])
    f.write('  <MINQTY>%s</MINQTY>\n' % parts_dict[key])
    f.write('  <NOTIFY>N</NOTIFY>\n')
    if key not in allow_used:
      f.write('  <CONDITION>N</CONDITION>\n')
    if wanted_list_id:
      f.write('  <WANTEDLISTID>%s</WANTEDLISTID>\n' % wanted_list_id)
    f.write(' </ITEM>\n')
  f.write('</INVENTORY>\n')

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
Converts Lego Digital Designer files into Bricklink orders.

Usage:
  bltool <command> [<flags>] <LDD_file>
  
The meat is the 'optimize' command. This will:

1. If not cached yet, fetches prices and shops for all bricks in the LDD model
   and store it a cache file. This will be also refetched if the model changes
   or if a refetch is forced.

2. Runs the optimizer. There are two optimizers:
   --mode=builtin (default)
     Considers the 20 best shops, takes about a minute. The runtime is
     exponential, so adding 1 shop will roughly double how long it takes.
   --mode=glpk
     Use the external GLPK optimizer (http://www.gnu.org/software/glpk/).
     For this, 'glpsol' must be in the path. Runtime is typically longer,
     but it is able to consider a lot more shops without exponential runtime.
     --condiser_shops=40 should be fast, 100 is also feasible but may take
     hours to complete.
     This mode caches the solution so if the pricing info, the model and
     the relevant arguments don't change then it will reuse the previous
     solution.
     
3. Prints the result.
   --format=text (default)
     Prints a short summary of which shops were considered, selected and
     which brick should be ordered from which shop.
   --format=textv
     Verbose text format. Prints out details about why the shops were
     considered.
   --format=html
     Full output. This creates a HTML file that contains all details,
     including the BrickLink wanted lists for each shop.
"""

import os.path
import sys

import fetch_shops
import gflags
import lfxml
import optimizer
import wanted_list

FLAGS = gflags.FLAGS

gflags.DEFINE_string(
    'format', 'text',
    'Output format: text, textv or html (see help).')

gflags.DEFINE_boolean(
    'refetch_shops', False,
    'Refetches shop info even if the cached info exists. Note that '
    'if parameters changed then the shop info will be refetched '
    'regardless the value of this flag.')

gflags.DEFINE_list(
    'include_used', [],
    'Allows used bricks for the listed part numbers. The special value '
    '"all" will allow all bricks. Example: 3022-48,3070b-56')

gflags.DEFINE_list(
    'exclude_used', [],
    'Does not allow used bricks for these part numbers. Can be used with '
    '--include_used=all.')

gflags.DEFINE_string(
    'wanted_list_id', '',
    'Wanted list id for the output wanted list, or blank.')

COMMANDS = {
  'help': {
      'usage': 'help',
      'desc': 'Lists the available commands.',
      'flags': [],
      'func': lambda argv: HelpCommand(argv)},
  'list': {
      'usage': '[<flags>] list <LDD_file>',
      'desc': 'Lists all bricks, colors and quantities from an LDD file.',
      'flags': ['wanted_list_id', 'include_used', 'exclude_used'],
      'func': lambda argv: ListCommand(argv)},
  'optimize': {
      'usage': '[<flags>] optimize <LDD_file>',
      'desc': 'Fetches BrickLink shops and print optimal sellers (expensive).',
      'flags': ['format', 'refetch_shops', 'include_used', 'exclude_used'],
      'func': lambda argv: OptimizeCommand(argv)}
}

def Print(what, tabs=0):
  def IsSimpleType(obj):
    return (not isinstance(obj, dict)
        and not isinstance(obj, list)
        and not isinstance(obj, set))
  
  if isinstance(what, dict):
    for k in what:
      w = what[k]
      if IsSimpleType(w):
        print '%s%s: %s' % (' ' * tabs, k, w)
      else:
        print '%s%s' % (' ' * tabs, k)
        Print(what[k], tabs + 1)
  elif IsSimpleType(what):
    print '%s%s' % (' ' * tabs, what)
  else:
    if what:
      if IsSimpleType(what[0]):
        print '%s%s' % (' ' * tabs, ', '.join(str(e) for e in what))
      else:
        for k in what:
          Print(k, tabs + 1)

def ReportError(msg):
  print 'Error: %s' % msg
  print 'Use bltool help to list the available commands and flags.'
  sys.exit(1)

def AllowedUserBricks(parts):
  return [
      p for p in parts
      if ('all' in FLAGS.include_used or p in FLAGS.include_used)
          and p not in FLAGS.exclude_used]

def HelpCommand(argv):
  print __doc__
  print 'Commands:'
  for command in sorted(COMMANDS.keys()):
    print ' %s: bltool %s' % (command, COMMANDS[command]['usage'])
    print '  %s' % COMMANDS[command]['desc']
    if COMMANDS[command]['flags']:
      print '  Accepted flags:'
      for flag in sorted(COMMANDS[command]['flags']):
        print '   --%s' % flag
    print
  sys.exit(1)
  
def ListCommand(argv):
  if len(argv) >= 3:
    parts = lfxml.GetBricklinkParts(argv[2:])
    count = sum(parts[k] for k in parts)
    sys.stdout.write('<!-- Total parts: %s -->\n' % count)
    wanted_list.OutputWantedList(
        sys.stdout, parts, AllowedUsedBricks(parts), FLAGS.wanted_list_id)
  else:
    ReportError('Not enough args for list.')
    
def OptimizeCommand(argv):
  if len(argv) == 3:
    parts = lfxml.GetBricklinkParts(argv[2:3])
    shops_file_name = '%s.%x.shops' % (
        os.path.splitext(os.path.basename(argv[2]))[0],
        hash(str(parts)) & 0xffffffff)
    if not os.path.exists(shops_file_name):
      print 'Cached shops file %s not found, refetching' % shops_file_name
      fetch_shops.FetchShopInfo(parts, shops_file_name)
    elif FLAGS.refetch_shops:
      print 'Forced refetch of shops file %s' % shops_file_name
      fetch_shops.FetchShopInfo(parts, shops_file_name)
      
    try:
      opt = optimizer.CreateOptimizer()
    except NameError, e:
      ReportError(e)

    opt.Load(parts, argv[2], shops_file_name)
    
    print 'Critical shops:'
    if FLAGS.format == 'text':
      Print(opt._critical_shops.keys(), tabs=1)
    else:
      Print(opt._critical_shops, tabs=1)
    print 'Supplemental shops:'
    if FLAGS.format == 'text':
      Print(opt._supplemental_shops.keys(), tabs=1)
    else:
      Print(opt._supplemental_shops, tabs=1)

    opt.Run()

    print 'Order bricks:'
    Print(opt._order_bricks, tabs=1)

  else:
    ReportError('Optimize needs exactly one argument.')

def main(argv):
  try:
    argv = FLAGS(argv)
  except gflags.FlagsError, e:
    ReportError(e)
  if len(argv) < 2:
    ReportError('No command.')
    
  if argv[1] in COMMANDS:
    COMMANDS[argv[1]]['func'](argv)
  else:
    ReportError('Unknown command \'%s\'' % argv[1])


if __name__ == '__main__':
  sys.exit(main(sys.argv))
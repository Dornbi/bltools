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
  
To get help:
  bltool help: about all commands
  bltool --help: about all flags

The meat is the 'optimize' command. This command reads the LDD file and
calculates the near-optimal orders from BrickLink shops to order add parts
listed in the LDD file.

Optimize does the following:

1. If not cached yet, fetches prices and shops for all bricks in the LDD model
   and stores them in cache files. This cache has a default "life time" of one
   day, which can be changed with the --shopcache_timeout option.

2. Runs the optimizer. There are two optimizers:
   --mode=builtin (default)
     Considers the 20 best shops, takes about a minute. The runtime is
     exponential, so adding 1 shop will roughly double how long it takes.
   --mode=glpk
     Use the external GLPK optimizer (http://www.gnu.org/software/glpk/). For
     this, 'glpsol' must be in the path. Runtime is typically longer, but it
     is able to consider a lot more shops without exponential runtime.
     --condiser_shops=40 should be fast, 100 is also feasible but may take
     hours to complete. This mode caches the solution so if the pricing info,
     the model and the relevant arguments don't change then it will reuse the
     previous solution.
     
3. Prints the result.
   By default, it prints a short summary of which shops were considered,
   selected and which brick should be ordered from which shop.
   --output_html=<filename>
     If set, writes all details into a HTML file. The file contains:
     * list of all shops considered, with scores
     * list of all shops to order from
     * list of all bricks to order from each shop
     * BrickLink wanted list XML list for each shop

Caveats:
* Part identifiers have the form NNNN-MM where NNNN is the BrickLink
  part ID and MM is the color code (as on BLID on http://peeron.com/inv/colors).
  If you generate HTML output, these identifiers will link directly to the
  colored part on BrickLink.
* All prices are shown in local currency. This is determined by BrickLink
  based on your IP address.
* The shipping costs are modeled as a fix cost per shop. The cost can be
  controlled by the --shop_fix_cost flag.
* The minimum purchase per shop is only taken into account
  with --model=glpk.
* Some shops allow items to be purchased in batches only. This is not
  taken into account. To work around, you can order more or use
  --exclude_shops.
* When --model=glpk, the ordered quantity may be more than the needed one,
  to fulfill mininum order requirements of shops.
"""

import os.path
import sys

import fetch_shops
import fetch_wanted_list
import fetch_inventory
import gflags
import lfxml
import optimizer
import output
import part_collector
import wanted_list

FLAGS = gflags.FLAGS

gflags.DEFINE_string(
    'output_html', '',
    'Output full details in HTML besides normal text output.')
    
gflags.DEFINE_string(
    'cachedir', '.bltools-cache',
    'Directory where cached files are saved.')

gflags.DEFINE_integer(
    'shopcache_timeout', 60*60*24,
    'Sets the timeout for the cache for shop data of parts, in seconds. '
    'Default is one day (60*60*24)')

gflags.DEFINE_list(
    'include_used', [],
    'Allows used bricks for the listed part numbers. The special value '
    '"all" will allow all bricks.')

gflags.DEFINE_list(
    'exclude_used', [],
    'Does not allow used bricks for these part numbers. Can be used with '
    '--include_used=all.')

gflags.DEFINE_string(
    'wanted_list_id', '',
    'Wanted list id for the output wanted list, or blank.')

gflags.DEFINE_list(
    'inventory', [],
    'Specifies XML files contaning existing inventory, which would be treated '
    'such for potential orders')

COMMANDS = {
  'help': {
      'usage': 'help',
      'desc': 'Lists the available commands.',
      'flags': [],
      'func': lambda argv: HelpCommand(argv)},
  'list': {
      'usage': '[<flags>] list <LDD_file>',
      'desc': 'Lists all bricks, colors and quantities from an LDD file. Two '
              'special values exist:\n'
              '  * "wlist" lists items in a given wanted list '
                '(--wanted_list_id)\n'
              '  * "store" lists all items available in a given store.',
      'flags': ['wanted_list_id', 'include_used', 'exclude_used'],
      'func': lambda argv: ListCommand(argv)},
  'optimize': {
      'usage': '[<flags>] optimize <LDD_file>',
      'desc': 'Fetches BrickLink shops and print optimal sellers (expensive).',
      'flags': [
          'output_html', 'cachedir', 'shopcache_timeout', 'include_used',
          'exclude_used', 'mode', 'rerun_solver', 'multiple', 'exclude_shops',
          'include_shops', 'include_countries', 'exclude_countries',
          'shop_fix_cost', 'max_shops', 'consider-shops', 'glpk_limit_seconds'],
      'func': lambda argv: OptimizeCommand(argv)}
}

def ReportError(msg):
  print 'Error: %s' % msg
  print 'Use bltool help to list the available commands and flags.'
  sys.exit(1)

def AllowedUsedBricks(parts):
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
    if argv[2] == "wlist":
      parts = fetch_wanted_list.FetchListInfo()
    elif argv[2] == 'store':
      parts = fetch_inventory.FetchStoreInfo()
    else:
      parts = ReadParts(argv[2:])
    count = sum(parts[k] for k in parts)
    extra_tags = ''
    if FLAGS.wanted_list_id:
      extra_tags = '<WANTEDLISTID>%s</WANTEDLISTID>' % FLAGS.wanted_list_id
    sys.stdout.write('<!-- Total parts: %s -->\n' % count)
    sys.stdout.write(
        wanted_list.WantedList(parts, extra_tags))
  else:
    ReportError('Not enough args for list.')
    
def OptimizeCommand(argv):
  if len(argv) >= 3:
    if argv[2] == "wlist":
      parts = fetch_wanted_list.FetchListInfo()
    # This arguably isn't the most useful option, but it works and in theory it
    # gives you what your own inventory would be worth if bought now on BL
    elif argv[2] == 'store':
      parts = fetch_inventory.FetchStoreInfo()
    else:
      parts = ReadParts(argv[2:])
    try:
      os.makedirs(FLAGS.cachedir)
    except OSError:
      pass
    # reduce wanted parts by parts indicated to be already present
    if (FLAGS.inventory):
      iparts = ReadParts(FLAGS.inventory)
      collector = part_collector.PartCollector()
      collector.InitParts(parts)
      parts = collector.Subtract(iparts)
    shop_data = fetch_shops.FetchShopInfo(parts)
      
    try:
      opt = optimizer.CreateOptimizer()
    except NameError, e:
      ReportError(e)

    allow_used = AllowedUsedBricks(parts)
    opt.Load(parts, argv[2], shop_data, allow_used)
    output.PrintShopsText(opt)
    opt.Run()
    output.PrintOrdersText(opt, FLAGS.shop_fix_cost)
    
    if FLAGS.output_html:
      output.PrintAllHtml(
          opt, FLAGS.shop_fix_cost, argv[2], FLAGS.output_html)

  else:
    ReportError('Optimize needs exactly one argument.')

def ReadParts(filenames):
  collector = part_collector.PartCollector()
  for filename in filenames:
    if filename.endswith('.xml'):
      wanted_list.CollectBricklinkParts(filename, collector)
    elif filename.endswith('.lxf'):
      lfxml.CollectBricklinkParts(filename, collector)
    elif (filename != ""):
      print 'Unknown file type for file %s' % filename
  return collector.Parts()

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

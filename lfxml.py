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
Parses Lego Digital Designer (LDD) files.
"""

import xml.sax
import xml.sax.handler
import zipfile

import gflags

import part_collector

FLAGS = gflags.FLAGS

gflags.DEFINE_string('color_translate', '',
                     'Custom dictionary to translate colors (bricklink colors). '
                     'Example: 53:201,1:3')

TRANSLATE_COLORS = {
    '1'   : '1',   # White
    '100' : '26',  # Light Salmon
    '101' : '25',  # Salmon
    '102' : '42',  # Medium Blue
    '103' : '49',  # Very Light Gray
    '104' : '24',  # Purple
    '105' : '31',  # Medium Orange
    '106' : '4',   # Orange
    '107' : '39',  # Dark Turquoise
    '11'  : '72',  # Maersk Blue
    '111' : '13',  # Trans-Black
    '112' : '43',  # Violet
    '113' : '50',  # Trans-Dark Pink
    '114' : '114', # Trans-Very Lt Blue
    '115' : '76',  # Medium Lime
    '116' : '40',  # Light Turquoise
    '117' : '101', # Glitter Trans-Clear
    '118' : '41',  # Aqua
    '119' : '34',  # Lime
    '12'  : '29',  # Earth Orange
    '120' : '35',  # Light Lime
    '124' : '71',  # Magenta
    '126' : '51',  # Trans-Purple
    '127' : '61',  # Pearl Light Gold
    '129' : '102', # Glitter Trans-Purple
    '131' : '66',  # Pearl Light Gray
    '132' : '111', # Speckle Black-Silver
    '135' : '55',  # Sand Blue
    '136' : '54',  # Sand Purple
    '138' : '69',  # Dark Tan
    '139' : '84',  # Copper
    '140' : '63',  # Dark Blue
    '141' : '80',  # Dark Green
    '143' : '74',  # Trans-Medium Blue
    '145' : '78',  # Metal Blue
    '148' : '77',  # Pearl Dark Gray
    '151' : '48',  # Sand Green
    '153' : '58',  # Sand Red
    '154' : '59',  # Dark Red
    '18'  : '28',  # Flesh
    '182' : '98',  # Trans-Orange
    '191' : '110', # Bright Light Orange
    '192' : '88',  # Reddish Brown
    '194' : '86',  # Light Bluish Gray
    '195' : '97',  # BlueViolet
    '196' : '109', # Dark Blue-Violet
    '198' : '93',  # Light Purple
    '199' : '85',  # Dark Bluish Gray
    '2'   : '9',   # Light Gray
    '20'  : '60',  # Milky White
    '208' : '99',  # Very Light Bluish Gray
    '21'  : '5',   # Red
    '212' : '105', # Bright Light Blue
    '217' : '91',  # Dark Flesh
    '22'  : '47',  # Dark Pink
    '222' : '104', # Bright Pink
    '226' : '103', # Bright Light Yellow
    '23'  : '7',   # Blue
    '232' : '87',  # Sky Blue
    '24'  : '3',   # Yellow
    '25'  : '8',   # Brown
    '26'  : '11',  # Black
    '268' : '89',  # Dark Purple
    '27'  : '10',  # Dark Gray
    '28'  : '6',   # Green
    '283' : '90',  # Light Flesh
    '29'  : '37',  # Medium Green
    '294' : '118', # Glow In Dark Trans
    '297' : '115', # Pearl Gold
    '3'   : '33',  # Light Yellow
    '301' : '22',  # Chrome Silver
    '308' : '120', # Dark Brown
    '36'  : '96',  # Very Light Orange
    '37'  : '36',  # Bright Green
    '38'  : '68',  # Dark Orange
    '39'  : '44',  # Light Violet
    '40'  : '12',  # Trans-Clear
    '41'  : '17',  # Trans-Red
    '42'  : '15',  # Trans-Light Blue
    '43'  : '14',  # Trans-Dark Blue
    '44'  : '19',  # Trans-Yellow
    '45'  : '62',  # Light Blue
    '47'  : '18',  # Trans-Neon Orange
    '48'  : '20',  # Trans-Green
    '49'  : '16',  # Trans-Neon Green
    '5'   : '2',   # Tan
    '50'  : '46',  # Glow In Dark Opaque
    '6'   : '38',  # Light Green
    '9'   : '23',  # Pink
}

TRANSLATE_PARTS = {
	'2362': '2362b',
	'2412': '2412b',
	'2429': '2429c01',
	'2431': '2431',
	'2476': '2476a',
	'2748': '3857',
	'2780': '4459',
	'30027': '30027b',
	'30133': 'x97',
	'30359': '30359b',
	'30389': '30389a',
	'3046': '3046A',
	'30552': '481',
	'30553': '482',
	'3062': '3062b',
	'3068': '3068b',
	'3069': '3069B',
	'3070': '3070b',
	'3190': '3192',
	'3191': '3193',
	'32123': '4265c',
	'3475': '3475b',
	'3626': '3626b',
	'3709': '3709b',
	'3729': '3731',
	'3816': '3817',
	'3829': '3829c01',
	'3839': '3839B',
	'3942': '3942B',
	'4025': '4092',
	'40620': '71137',
	'4081': '4081b',
	'4085': '4085c',
	'41239': '32277',
	'41532': 'x241',
	'41762': '42022',
	'42022': '464',
	'42023': '500',
	'42611': '51011',
	'4285': '4285B',
	'43093': '3749',
	'4343': '73436',
	'4345': '4345b',
	'44237': '2456',
	'44676': '405',
	'4486': '73312',
	'45244': '3626bps9',
	'4530': '6093',
	'4592': '298c02',
	'4697': '4696b',
	'48183': '4859',
	'50254': '2927',
	'50746': '54200',
	'55298': '6246a',
	'56750': '3742c01',
	'58123': '58123c01',
	'59275': '2599',
	'59443': '6538c',
	'6014': '6014b',
	'60797': '60797c02',
	'6093': 'x104',
	'6141': '4073',
	'6143': '3941',
	'6211': '73590c02a',
	'6238': '6238a',
	'6255': 'x8',
	'64414': '64415',
	'6538': '6538A',
	'6562': '3749',
	'6590': '3713',
	'70358': '590',
	'70750': '38',
	'73081': '3829',
	'73200': '970c00',
	'73587': '4592c01',
	'74746': '2865',
	'74784': '2878c01',
	'76382': '973p1b',
	'83447': '3626ap01',
	'83608': '3069bp0c',
	'86035': '4485',
	'99999992': '2878C01',
}

class LxfmlPartCollector(xml.sax.handler.ContentHandler):
  def __init__(self, collector = part_collector.PartCollector()):
    self._collector = collector
    self._custom_dict = self._ParseCustomDict()

  def _ParseCustomDict(self):
    custom_dict = {}
    for mapping in FLAGS.color_translate.split(','):
      split_mapping = mapping.split(':')
      if len(split_mapping) >1:
        custom_dict[split_mapping[0]] = split_mapping[1]
    return custom_dict

  def startElement(self, name, attrs):
    if name == 'Part' and 'designID' in attrs and 'materials' in attrs:
      part_id = attrs['designID']
      color_id = attrs['materials'].split(',')[0]
      if color_id in TRANSLATE_COLORS:
        color_id = TRANSLATE_COLORS[color_id]
        if color_id in self._custom_dict:
          color_id = self._custom_dict[color_id]
        if part_id in TRANSLATE_PARTS:
          part_id = TRANSLATE_PARTS[part_id]
        self._collector.AddPart(part_id, color_id)
      else:
        print 'Unknown color: %s for part %s' % color_id, part_id


def CollectBricklinkParts(filename, collector):
  lxfml_part_collector = LxfmlPartCollector(collector)
  zf = zipfile.ZipFile(filename, 'r')
  try:
    f = zf.open('IMAGE100.LXFML', 'r')
    xml.sax.parse(f, lxfml_part_collector)
  finally:
    zf.close()


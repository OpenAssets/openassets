"""
The MIT License (MIT)

Copyright (c) 2014 Flavien Charlon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import bitcoin.core
import io
import openassets.protocol
import unittest

class MarkerOutputTests(unittest.TestCase):

    # def setUp(self):
    #     self.seq = list(range(10))

    def test_leb128_decode(self):

        def assert_leb128_decode(expected, data):
            with io.BytesIO(data) as stream:
                result = openassets.protocol.MarkerOutput.leb128_decode(stream)
                self.assertEquals(expected, result)

        assert_leb128_decode(0, b'\x00')
        assert_leb128_decode(1, b'\x01')
        assert_leb128_decode(127, b'\x7F')
        assert_leb128_decode(128, b'\x80\x01')
        assert_leb128_decode(0xff, b'\xff\x01')
        assert_leb128_decode(0x100, b'\x80\x02')
        assert_leb128_decode(300, b'\xac\x02')
        assert_leb128_decode(624485, b'\xe5\x8e\x26')
        assert_leb128_decode(0xffffff, b'\xff\xff\xff\x07')
        assert_leb128_decode(0x1000000, b'\x80\x80\x80\x08')
        assert_leb128_decode(2**64, b'\x80\x80\x80\x80\x80\x80\x80\x80\x80\x02')

    def test_parse_script_success(self):

        def assert_parse_script(expected, data):
            script = bitcoin.core.CScript(data)
            self.assertEquals(expected, openassets.protocol.MarkerOutput.parse_script(script))

        assert_parse_script(b'', b'\x6a\x00')
        assert_parse_script(b'abcdef', b'\x6a\x06abcdef')
        assert_parse_script(b'abcdef', b'\x6a\x4c\x06abcdef')
        assert_parse_script(b'abcdef', b'\x6a\x4d\x06\x00abcdef')
        assert_parse_script(b'abcdef', b'\x6a\x4e\x06\x00\x00\x00abcdef')

    def test_parse_script_invalid(self):

        def assert_parse_script(data):
            script = bitcoin.core.CScript(data)
            self.assertEquals(None, openassets.protocol.MarkerOutput.parse_script(script))

        # The first operator is not OP_RETURN
        assert_parse_script(b'\x6b\x00')
        # No PUSHDATA
        assert_parse_script(b'\x6a')
        assert_parse_script(b'\x6a\x75')
        # Invalid PUSHDATA
        assert_parse_script(b'\x6a\x06')
        assert_parse_script(b'\x6a\x05abcdef')
        assert_parse_script(b'\x6a\x4d')
        # Additional operators
        assert_parse_script(b'\x6a\x06abcdef\x01a')
        assert_parse_script(b'\x6a\x06abcdef\x75')

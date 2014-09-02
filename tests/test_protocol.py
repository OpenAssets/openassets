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

import binascii
import bitcoin.core
import io
import openassets.protocol
import unittest


class ColoringEngineTests(unittest.TestCase):
    # def setUp(self):
    # self.seq = list(range(10))

    def test_compute_asset_addresses_issuance(self):
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": None, "asset_quantity": 0, "output_script": b"abcdef"},
                {"asset_address": None, "asset_quantity": 0, "output_script": b"ghijkl"}
            ],
            asset_quantities=[1, 3],
            marker_index=2,
            output_count=3
        )

        issuance_asset_address = openassets.protocol.ColoringEngine.hash_script(b"abcdef")
        self.assert_output(outputs[0], issuance_asset_address, 1, openassets.protocol.OutputType.issuance)
        self.assert_output(outputs[1], issuance_asset_address, 3, openassets.protocol.OutputType.issuance)
        self.assert_output(outputs[2], None, 0, openassets.protocol.OutputType.marker_output)

    def test_compute_asset_addresses_transfer(self):
        # No asset quantity defined
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 2}
            ],
            asset_quantities=[],
            output_count=1
        )
        self.assert_output(outputs[0], None, 0, openassets.protocol.OutputType.marker_output)

        # More asset quantities than outputs
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 2}
            ],
            asset_quantities=[1],
            output_count=1
        )
        self.assertIsNone(outputs)

        # Single input and single output
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 2}
            ],
            asset_quantities=[2],
            output_count=2
        )
        self.assert_output(outputs[0], None, 0, openassets.protocol.OutputType.marker_output)
        self.assert_output(outputs[1], b"a", 2, openassets.protocol.OutputType.transfer)

        # Empty outputs
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 2}
            ],
            asset_quantities=[0, 1, 0, 1],
            output_count=6
        )
        self.assert_output(outputs[0], None, 0, openassets.protocol.OutputType.marker_output)
        self.assert_output(outputs[1], None, 0, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[2], b"a", 1, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[3], None, 0, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[4], b"a", 1, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[5], None, 0, openassets.protocol.OutputType.transfer)

        # Empty inputs
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": None, "asset_quantity": 0},
                {"asset_address": b"a", "asset_quantity": 2},
                {"asset_address": None, "asset_quantity": 0}
            ],
            asset_quantities=[2],
            output_count=3
        )
        self.assert_output(outputs[0], None, 0, openassets.protocol.OutputType.marker_output)
        self.assert_output(outputs[1], b"a", 2, openassets.protocol.OutputType.transfer)

        # Outputs less than inputs
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 3},
                {"asset_address": b"a", "asset_quantity": 1}
            ],
            asset_quantities=[1, 1],
            output_count=3
        )
        self.assert_output(outputs[0], None, 0, openassets.protocol.OutputType.marker_output)
        self.assert_output(outputs[1], b"a", 1, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[2], b"a", 1, openassets.protocol.OutputType.transfer)

        # Output partially unassigned
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 1},
                {"asset_address": b"a", "asset_quantity": 2}
            ],
            asset_quantities=[1, 3],
            output_count=3
        )
        self.assertIsNone(outputs)

        # Entire output unassigned
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 1}
            ],
            asset_quantities=[1, 3],
            output_count=3
        )
        self.assertIsNone(outputs)

        # Multiple inputs and outputs - Matching values
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 1},
                {"asset_address": b"b", "asset_quantity": 2},
                {"asset_address": b"c", "asset_quantity": 3}
            ],
            asset_quantities=[1, 2, 3],
            output_count=4
        )
        self.assert_output(outputs[0], None, 0, openassets.protocol.OutputType.marker_output)
        self.assert_output(outputs[1], b"a", 1, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[2], b"b", 2, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[3], b"c", 3, openassets.protocol.OutputType.transfer)

        # Multiple inputs and outputs - Mixing same color
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 2},
                {"asset_address": b"a", "asset_quantity": 1},
                {"asset_address": b"a", "asset_quantity": 2}
            ],
            asset_quantities=[1, 3, 1],
            output_count=4
        )
        self.assert_output(outputs[0], None, 0, openassets.protocol.OutputType.marker_output)
        self.assert_output(outputs[1], b"a", 1, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[2], b"a", 3, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[3], b"a", 1, openassets.protocol.OutputType.transfer)

        # Multiple inputs and outputs - Mixing different colors
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 2},
                {"asset_address": b"b", "asset_quantity": 1},
                {"asset_address": b"c", "asset_quantity": 2}
            ],
            asset_quantities=[1, 3, 1],
            output_count=4
        )
        self.assertIsNone(outputs)

    def test_compute_asset_addresses_issuance_transfer(self):
        outputs = self.color_outputs(
            inputs=[
                {"asset_address": b"a", "asset_quantity": 3, "output_script": b"abcdef"},
                {"asset_address": b"a", "asset_quantity": 2, "output_script": b"ghijkl"}
            ],
            asset_quantities=[1, 4, 2, 3],
            marker_index=2,
            output_count=5
        )

        issuance_asset_address = openassets.protocol.ColoringEngine.hash_script(b"abcdef")
        self.assert_output(outputs[0], issuance_asset_address, 1, openassets.protocol.OutputType.issuance)
        self.assert_output(outputs[1], issuance_asset_address, 4, openassets.protocol.OutputType.issuance)
        self.assert_output(outputs[2], None, 0, openassets.protocol.OutputType.marker_output)
        self.assert_output(outputs[3], b"a", 2, openassets.protocol.OutputType.transfer)
        self.assert_output(outputs[4], b"a", 3, openassets.protocol.OutputType.transfer)

    def test_hash_script(self):
        previous_output = binascii.unhexlify('76a914010966776006953D5567439E5E39F86A0D273BEE88AC')
        output = openassets.protocol.ColoringEngine.hash_script(previous_output)
        self.assertEquals(binascii.unhexlify('36e0ea8e93eaa0285d641305f4c81e563aa570a2'), output)

    def color_outputs(self, inputs, asset_quantities, output_count, marker_index=0):
        previous_outputs = [
            openassets.protocol.TransactionOutput(
                bitcoin.core.CTxOut(10, bitcoin.core.CScript(item.get("output_script", b"\x01\x02"))),
                item["asset_address"],
                item["asset_quantity"],
                None)
            for item in inputs]

        outputs = []
        for i in range(0, output_count):
            outputs.append(bitcoin.core.CTxOut(20, bitcoin.core.CScript(b"\x00" * output_count)))

        return openassets.protocol.ColoringEngine._compute_asset_addresses(
            previous_outputs,
            marker_index,
            outputs,
            asset_quantities)

    def assert_output(self, output, asset_address, asset_quantity, output_type):
        self.assertEquals(asset_address, output.asset_address)
        self.assertEquals(asset_quantity, output.asset_quantity)
        self.assertEquals(output_type, output.output_type)


class MarkerOutputTests(unittest.TestCase):
    def test_leb128_decode_success(self):
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
        assert_leb128_decode(2 ** 64, b'\x80\x80\x80\x80\x80\x80\x80\x80\x80\x02')

    def test_leb128_decode_invalid(self):
        data = b'\xe5\x8e'

        with io.BytesIO(data) as stream:
            self.assertRaises(bitcoin.core.SerializationTruncationError,
                              openassets.protocol.MarkerOutput.leb128_decode, stream)

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
            self.assertIsNone(openassets.protocol.MarkerOutput.parse_script(bitcoin.core.CScript(data)))

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

    def test_deserialize_payload_success(self):
        def assert_deserialize_payload(expected_asset_quantities, expected_metadata, data):
            marker_output = openassets.protocol.MarkerOutput.deserialize_payload(data)
            self.assertEquals(expected_asset_quantities, marker_output.asset_quantities)
            self.assertEquals(expected_metadata, marker_output.metadata)

        assert_deserialize_payload([1, 300], b'abcdef', b'OA\x01\x00' + b'\x02\x01\xac\x02' + b'\06abcdef')
        assert_deserialize_payload([5] * 256, b'abcdef',
                                   b'OA\x01\x00' + b'\xfd\x00\x01' + (b'\x05' * 256) + b'\06abcdef')
        assert_deserialize_payload([1], b'\x01' * 256,
                                   b'OA\x01\x00' + b'\x01\x01' + b'\xfd\x00\x01' + b'\x01' * 256)
        assert_deserialize_payload([2 ** 63 - 1], b'',
                                   b'OA\x01\x00' + b'\x01' + (b'\xFF' * 8) + b'\x7F' + b'\x00')

    def test_deserialize_payload_invalid(self):
        def assert_deserialize_payload(data):
            self.assertIsNone(openassets.protocol.MarkerOutput.deserialize_payload(data))

        # Invalid OAP tag
        assert_deserialize_payload(b'OB\x01\x00' + b'\x02\x01\xac\x02' + b'\06abcdef')
        assert_deserialize_payload(b'OA\x02\x00' + b'\x02\x01\xac\x02' + b'\06abcdef')
        # Invalid length
        assert_deserialize_payload(b'O')
        assert_deserialize_payload(b'OA\x01')
        assert_deserialize_payload(b'OA\x01\x00' + b'\x02\x01')
        assert_deserialize_payload(b'OA\x01\x00' + b'\x02\x01\xac')
        assert_deserialize_payload(b'OA\x01\x00' + b'\x02\x01\xac\x02' + b'\06abcd')
        assert_deserialize_payload(b'OA\x01\x00' + b'\x02\x01\xac\x02' + b'\06abcdefgh')
        assert_deserialize_payload(b'OA\x01\x00' + b'\xfd\x00')
        # Asset quantity too large
        assert_deserialize_payload(b'OA\x01\x00' + b'\x01' + (b'\x80' * 9) + b'\01' + b'\x00')

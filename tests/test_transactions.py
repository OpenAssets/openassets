# -*- coding: utf-8; -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2014 Flavien Charlon
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import bitcoin.core
import bitcoin.core.script
import openassets.protocol
import openassets.transactions
import unittest
import unittest.mock


class TransactionBuilderTests(unittest.TestCase):
    def setUp(self):
        self.target = openassets.transactions.TransactionBuilder(10)

    # issue_asset

    def test_issue_asset_success(self):
        outputs = self.generate_outputs([
            (20, b'source', b'a1', 50),
            (15, b'source', None, 0),
            (20, b'other', None, 0),
            (10, b'source', None, 0)
        ])

        result = self.target.issue(outputs, 1000, b'metadata', b'source', b'target', 5)

        self.assertEquals(2, len(result.vin))
        self.assert_input(result.vin[0], b'1' * 32, 1, b'source')
        self.assert_input(result.vin[1], b'3' * 32, 3, b'source')
        self.assertEquals(3, len(result.vout))
        self.assert_marker(result.vout[0], [1000], b'metadata')
        self.assert_output(result.vout[1], 10, b'target')
        self.assert_output(result.vout[2], 10, b'source')

    def test_issue_asset_insufficient_funds(self):
        outputs = self.generate_outputs([
            (20, b'source', b'a1', 50),
            (15, b'source', None, 0),
            (20, b'other', None, 0),
            (5, b'source', None, 0)
        ])

        self.assertRaises(
            openassets.transactions.InsufficientFundsError,
            self.target.issue, outputs, 1000, b'metadata', b'source', b'target', 5)

    def test_transfer_bitcoin(self):
        outputs = self.generate_outputs([
            (150, b'source', b'a1', 50),
            (150, b'source', None, 0),
            (150, b'other', None, 0),
            (150, b'source', None, 0)
        ])

        result = self.target.transfer_bitcoin(outputs, b'source', b'target', 200, 10)

        self.assertEquals(2, len(result.vin))
        self.assert_input(result.vin[0], b'1' * 32, 1, b'source')
        self.assert_input(result.vin[1], b'3' * 32, 3, b'source')
        self.assertEquals(2, len(result.vout))
        self.assert_output(result.vout[0], 90, b'source')
        self.assert_output(result.vout[1], 200, b'target')

    # Test helpers

    def generate_outputs(self, definitions):
        result = []
        # Each definition has the following format:
        # (value, output_script, asset_address, asset_quantity)
        for i, item in enumerate(definitions):
            byte = bytes(str(i), encoding='UTF-8')
            result.append(openassets.transactions.SpendableOutput(
                out_point=bitcoin.core.COutPoint(byte * 32, i),
                output=openassets.protocol.TransactionOutput(
                    item[0], bitcoin.core.script.CScript(item[1]), item[2], item[3])
            ))

        return result

    def assert_input(self, input, transaction_hash, output_index, script):
        self.assertEquals(transaction_hash, input.prevout.hash)
        self.assertEquals(output_index, input.prevout.n)
        self.assertEquals(script, bytes(input.scriptSig))

    def assert_output(self, output, nValue, scriptPubKey):
        self.assertEquals(nValue, output.nValue)
        self.assertEquals(scriptPubKey, bytes(output.scriptPubKey))

    def assert_marker(self, output, asset_quantities, metadata):
        payload = openassets.protocol.MarkerOutput.parse_script(output.scriptPubKey)
        marker_output = openassets.protocol.MarkerOutput.deserialize_payload(payload)

        self.assertEquals(0, output.nValue)
        self.assertEquals(asset_quantities, marker_output.asset_quantities)
        self.assertEquals(metadata, marker_output.metadata)


class SpendableOutputTests(unittest.TestCase):
    def test_init_success(self):
        target = openassets.transactions.SpendableOutput(
            bitcoin.core.COutPoint('\x01' * 32),
            openassets.protocol.TransactionOutput(100))

        self.assertEquals('\x01' * 32, target.out_point.hash)
        self.assertEquals(100, target.output.nValue)

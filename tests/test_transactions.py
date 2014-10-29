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
            (10, b'source', None, 0)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 1000)
        result = self.target.issue(spec, b'metadata', 5)

        self.assertEqual(2, len(result.vin))
        self.assert_input(result.vin[0], b'1' * 32, 1, b'source')
        self.assert_input(result.vin[1], b'2' * 32, 2, b'source')
        self.assertEqual(3, len(result.vout))
        # Asset issued
        self.assert_output(result.vout[0], 10, b'target')
        # Marker output
        self.assert_marker(result.vout[1], [1000], b'metadata')
        # Bitcoin change
        self.assert_output(result.vout[2], 10, b'change')

    def test_issue_asset_insufficient_funds(self):
        outputs = self.generate_outputs([
            (20, b'source', b'a1', 50),
            (15, b'source', None, 0),
            (5, b'source', None, 0)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 1000)
        self.assertRaises(
            openassets.transactions.InsufficientFundsError,
            self.target.issue, spec, b'metadata', 5)

    def test_transfer_bitcoin_with_change(self):
        outputs = self.generate_outputs([
            (150, b'source', b'a1', 50),
            (150, b'source', None, 0),
            (150, b'source', None, 0)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 200)
        result = self.target.transfer_bitcoin(spec, 10)

        self.assertEqual(2, len(result.vin))
        self.assert_input(result.vin[0], b'1' * 32, 1, b'source')
        self.assert_input(result.vin[1], b'2' * 32, 2, b'source')
        self.assertEqual(2, len(result.vout))
        # Bitcoin change
        self.assert_output(result.vout[0], 90, b'change')
        # Bitcoins sent
        self.assert_output(result.vout[1], 200, b'target')

    def test_transfer_bitcoin_no_change(self):
        outputs = self.generate_outputs([
            (150, b'source', b'a1', 50),
            (60, b'source', None, 0),
            (150, b'source', None, 0)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 200)
        result = self.target.transfer_bitcoin(spec, 10)

        self.assertEqual(2, len(result.vin))
        self.assert_input(result.vin[0], b'1' * 32, 1, b'source')
        self.assert_input(result.vin[1], b'2' * 32, 2, b'source')
        self.assertEqual(1, len(result.vout))
        # Bitcoins sent
        self.assert_output(result.vout[0], 200, b'target')

    def test_transfer_bitcoin_dust_limit(self):
        outputs = self.generate_outputs([
            (25, b'source', None, 0),
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 10)
        result = self.target.transfer_bitcoin(spec, 5)

        self.assertEqual(1, len(result.vin))
        self.assert_input(result.vin[0], b'0' * 32, 0, b'source')
        self.assertEqual(2, len(result.vout))
        # Bitcoin change
        self.assert_output(result.vout[0], 10, b'change')
        # Bitcoins sent
        self.assert_output(result.vout[1], 10, b'target')

    def test_transfer_bitcoin_insufficient_funds(self):
        outputs = self.generate_outputs([
            (150, b'source', b'a1', 50),
            (60, b'source', None, 0),
            (150, b'source', None, 0)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 201)
        self.assertRaises(
            openassets.transactions.InsufficientFundsError,
            self.target.transfer_bitcoin, spec, 10)

    def test_transfer_bitcoin_dust_output(self):
        outputs = self.generate_outputs([
            (19, b'source', None, 0)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 9)
        self.assertRaises(
            openassets.transactions.DustOutputError,
            self.target.transfer_bitcoin, spec, 10)

    def test_transfer_bitcoin_dust_change(self):
        outputs = self.generate_outputs([
            (150, b'source', None, 0)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'change', 150 - 10 - 9)
        self.assertRaises(
            openassets.transactions.DustOutputError,
            self.target.transfer_bitcoin, spec, 10)

    def test_transfer_assets_with_change(self):
        outputs = self.generate_outputs([
            (10, b'source', b'a1', 50),
            (80, b'source', None, 0),
            (20, b'source', b'a1', 100)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'asset_change', 120)
        result = self.target.transfer_assets(b'a1', spec, b'bitcoin_change', 40)

        self.assertEqual(3, len(result.vin))
        self.assert_input(result.vin[0], b'0' * 32, 0, b'source')
        self.assert_input(result.vin[1], b'2' * 32, 2, b'source')
        self.assert_input(result.vin[2], b'1' * 32, 1, b'source')
        self.assertEqual(4, len(result.vout))
        # Marker output
        self.assert_marker(result.vout[0], [120, 30], b'')
        # Asset sent
        self.assert_output(result.vout[1], 10, b'target')
        # Asset change
        self.assert_output(result.vout[2], 10, b'asset_change')
        # Bitcoin change
        self.assert_output(result.vout[3], 50, b'bitcoin_change')

    def test_transfer_assets_no_change(self):
        outputs = self.generate_outputs([
            (10, b'source', b'a1', 50),
            (80, b'source', None, 0),
            (10, b'source', b'a1', 70)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'asset_change', 120)
        result = self.target.transfer_assets(b'a1', spec, b'bitcoin_change', 40)

        self.assertEqual(3, len(result.vin))
        self.assert_input(result.vin[0], b'0' * 32, 0, b'source')
        self.assert_input(result.vin[1], b'2' * 32, 2, b'source')
        self.assert_input(result.vin[2], b'1' * 32, 1, b'source')
        self.assertEqual(3, len(result.vout))
        # Marker output
        self.assert_marker(result.vout[0], [120], b'')
        # Asset sent
        self.assert_output(result.vout[1], 10, b'target')
        # Bitcoin change
        self.assert_output(result.vout[2], 50, b'bitcoin_change')

    def test_transfer_assets_insufficient_asset_quantity(self):
        outputs = self.generate_outputs([
            (10, b'source', b'a1', 50),
            (80, b'source', None, 0),
            (10, b'other', None, 0),
            (10, b'source', b'a1', 70)
        ])

        spec = openassets.transactions.TransferParameters(outputs, b'target', b'asset_change', 121)
        self.assertRaises(
            openassets.transactions.InsufficientAssetQuantityError,
            self.target.transfer_assets, b'a1', spec, b'bitcoin_change', 40)

    def test_btc_asset_swap(self):
        outputs = self.generate_outputs([
            (90, b'source_btc', None, 0),
            (100, b'source_btc', None, 0),
            (10, b'source_asset', b'a1', 50),
            (10, b'source_asset', b'a1', 100),
        ])

        btc_spec = openassets.transactions.TransferParameters(outputs[0:2], b'source_asset', b'source_btc', 160)
        asset_spec = openassets.transactions.TransferParameters(outputs[2:4], b'source_btc', b'source_asset', 120)
        result = self.target.btc_asset_swap(btc_spec, b'a1', asset_spec, 10)

        self.assertEqual(4, len(result.vin))
        self.assert_input(result.vin[0], b'2' * 32, 2, b'source_asset')
        self.assert_input(result.vin[1], b'3' * 32, 3, b'source_asset')
        self.assert_input(result.vin[2], b'0' * 32, 0, b'source_btc')
        self.assert_input(result.vin[3], b'1' * 32, 1, b'source_btc')
        self.assertEqual(5, len(result.vout))
        # Marker output
        self.assert_marker(result.vout[0], [120, 30], b'')
        # Asset sent
        self.assert_output(result.vout[1], 10, b'source_btc')
        # Asset change
        self.assert_output(result.vout[2], 10, b'source_asset')
        # Bitcoin change
        self.assert_output(result.vout[3], 20, b'source_btc')
        # Bitcoins sent
        self.assert_output(result.vout[4], 160, b'source_asset')

    def test_asset_asset_swap(self):
        outputs = self.generate_outputs([
            (10, b'source_1', b'a1', 100),
            (10, b'source_1', b'a1', 80),
            (80, b'source_1', None, 0),
            (10, b'source_2', b'a2', 600),
            (100, b'source_2', None, 0),
        ])

        asset1_spec = openassets.transactions.TransferParameters(outputs[0:3], b'source_2', b'source_1', 120)
        asset2_spec = openassets.transactions.TransferParameters(outputs[3:4], b'source_1', b'source_2', 260)
        result = self.target.asset_asset_swap(b'a1', asset1_spec, b'a2', asset2_spec, 20)

        self.assertEqual(4, len(result.vin))
        self.assert_input(result.vin[0], b'0' * 32, 0, b'source_1')
        self.assert_input(result.vin[1], b'1' * 32, 1, b'source_1')
        self.assert_input(result.vin[2], b'3' * 32, 3, b'source_2')
        self.assert_input(result.vin[3], b'2' * 32, 2, b'source_1')
        self.assertEqual(6, len(result.vout))
        # Marker output
        self.assert_marker(result.vout[0], [120, 60, 260, 340], b'')
        # Asset 1 sent
        self.assert_output(result.vout[1], 10, b'source_2')
        # Asset 1 change
        self.assert_output(result.vout[2], 10, b'source_1')
        # Asset 2 sent
        self.assert_output(result.vout[3], 10, b'source_1')
        # Asset 2 sent
        self.assert_output(result.vout[4], 10, b'source_2')
        # Bitcoin change
        self.assert_output(result.vout[5], 50, b'source_1')

    # Test helpers

    def generate_outputs(self, definitions):
        result = []
        # Each definition has the following format:
        # (value, output_script, asset_id, asset_quantity)
        for i, item in enumerate(definitions):
            byte = bytes(str(i), encoding='UTF-8')
            result.append(openassets.transactions.SpendableOutput(
                out_point=bitcoin.core.COutPoint(byte * 32, i),
                output=openassets.protocol.TransactionOutput(
                    item[0], bitcoin.core.script.CScript(item[1]), item[2], item[3])
            ))

        return result

    def assert_input(self, input, transaction_hash, output_index, script):
        self.assertEqual(transaction_hash, input.prevout.hash)
        self.assertEqual(output_index, input.prevout.n)
        self.assertEqual(script, bytes(input.scriptSig))

    def assert_output(self, output, nValue, scriptPubKey):
        self.assertEqual(nValue, output.nValue)
        self.assertEqual(scriptPubKey, bytes(output.scriptPubKey))

    def assert_marker(self, output, asset_quantities, metadata):
        payload = openassets.protocol.MarkerOutput.parse_script(output.scriptPubKey)
        marker_output = openassets.protocol.MarkerOutput.deserialize_payload(payload)

        self.assertEqual(0, output.nValue)
        self.assertEqual(asset_quantities, marker_output.asset_quantities)
        self.assertEqual(metadata, marker_output.metadata)


class SpendableOutputTests(unittest.TestCase):
    def test_init_success(self):
        target = openassets.transactions.SpendableOutput(
            bitcoin.core.COutPoint('\x01' * 32),
            openassets.protocol.TransactionOutput(100))

        self.assertEqual('\x01' * 32, target.out_point.hash)
        self.assertEqual(100, target.output.value)

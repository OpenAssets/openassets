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

import asyncio
import binascii
import bitcoin.core
import io
import openassets.protocol
import tests.helpers
import unittest
import unittest.mock

from openassets.protocol import OutputType


class ColoringEngineTests(unittest.TestCase):

    # get_output

    @unittest.mock.patch('openassets.protocol.ColoringEngine.color_transaction', autospec=True)
    @unittest.mock.patch('openassets.protocol.OutputCache.get', autospec=True)
    @unittest.mock.patch('openassets.protocol.OutputCache.put', autospec=True)
    @tests.helpers.async_test
    def test_get_output_success(self, put_mock, get_mock, color_transaction_mock, loop):
        get_mock.return_value = self.as_future(None, loop)
        color_transaction_mock.return_value = self.as_future(self.create_test_outputs(), loop)

        @asyncio.coroutine
        def transaction_provider(transaction_hash):
            return self.create_test_transaction(b'')

        target = openassets.protocol.ColoringEngine(transaction_provider, openassets.protocol.OutputCache(), loop)

        result = yield from target.get_output(b'abcd', 2)

        self.assert_output(result, 3, b'\x30', b'b', 1, OutputType.transfer)
        self.assertEqual(get_mock.call_args_list[0][0][1:], (b'abcd', 2))
        self.assertEqual(3, len(put_mock.call_args_list))
        self.assertEqual(put_mock.call_args_list[0][0][1:3], (b'abcd', 0))
        self.assert_output(put_mock.call_args_list[0][0][3], 1, b'\x10', b'a', 6, OutputType.issuance)
        self.assertEqual(put_mock.call_args_list[1][0][1:3], (b'abcd', 1))
        self.assert_output(put_mock.call_args_list[1][0][3], 2, b'\x20', b'a', 2, OutputType.marker_output)
        self.assertEqual(put_mock.call_args_list[2][0][1:3], (b'abcd', 2))
        self.assert_output(put_mock.call_args_list[2][0][3], 3, b'\x30', b'b', 1, OutputType.transfer)

    @unittest.mock.patch('openassets.protocol.OutputCache.get', autospec=True)
    @unittest.mock.patch('openassets.protocol.OutputCache.put', autospec=True)
    @tests.helpers.async_test
    def test_get_output_not_found(self, put_mock, get_mock, loop):
        get_mock.return_value = self.as_future(None, loop)

        @asyncio.coroutine
        def transaction_provider(transaction_hash):
            return None

        target = openassets.protocol.ColoringEngine(transaction_provider, openassets.protocol.OutputCache(), loop)

        yield from tests.helpers.assert_coroutine_raises(self, ValueError, target.get_output, b'abcd', 2)

        self.assertEqual(get_mock.call_args_list[0][0][1:], (b'abcd', 2))

    @unittest.mock.patch('openassets.protocol.OutputCache.get', autospec=True)
    @unittest.mock.patch('openassets.protocol.OutputCache.put', autospec=True)
    @tests.helpers.async_test
    def test_get_output_cached(self, put_mock, get_mock, loop):
        get_mock.return_value = self.as_future(self.create_test_outputs()[2], loop)

        target = openassets.protocol.ColoringEngine(None, openassets.protocol.OutputCache(), loop)

        result = yield from target.get_output(b'abcd', 2)

        self.assert_output(result, 3, b'\x30', b'b', 1, OutputType.transfer)
        self.assertEqual(get_mock.call_args_list[0][0][1:], (b'abcd', 2))

    @unittest.mock.patch('openassets.protocol.OutputCache.get', autospec=True)
    @unittest.mock.patch('openassets.protocol.OutputCache.put', autospec=True)
    @tests.helpers.async_test
    def test_get_output_deep_chain(self, put_mock, get_mock, loop):
        get_mock.return_value = self.as_future(None, loop)

        depth_counter = [1000]
        def transaction_provider(transaction_hash):
            depth_counter[0] -= 1
            if depth_counter[0] > 1:
                result = bitcoin.core.CTransaction(
                    [
                        bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x01' * 32, 1))
                    ],
                    [
                        bitcoin.core.CTxOut(0, bitcoin.core.CScript(b'\x6a\x07OA\x01\x00' + b'\x01\x05' + b'\00')),
                        bitcoin.core.CTxOut(10, bitcoin.core.CScript(b'\x10'))
                    ])
            elif depth_counter[0] == 1:
                result = bitcoin.core.CTransaction(
                    [
                        bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x01' * 32, 0))
                    ],
                    [
                        bitcoin.core.CTxOut(20, bitcoin.core.CScript(b'\x20')),
                        bitcoin.core.CTxOut(30, bitcoin.core.CScript(b'\x30')),
                        bitcoin.core.CTxOut(0, bitcoin.core.CScript(b'\x6a\x08OA\x01\x00' + b'\x02\x00\x05' + b'\00')),
                    ])
            else:
                result = bitcoin.core.CTransaction([], [bitcoin.core.CTxOut(40, bitcoin.core.CScript(b'\x40'))])

            return self.as_future(result, loop)

        target = openassets.protocol.ColoringEngine(transaction_provider, openassets.protocol.OutputCache(), loop)

        result = yield from target.get_output(b'\x01', 1)

        issuance_asset_id = openassets.protocol.ColoringEngine.hash_script(b'\x40')
        self.assert_output(result, 10, b'\x10', issuance_asset_id, 5, OutputType.transfer)
        self.assertEqual(0, depth_counter[0])
        self.assertEqual(1000, len(get_mock.call_args_list))
        self.assertEqual(2 * 998 + 3 + 1, len(put_mock.call_args_list))

    # color_transaction

    @unittest.mock.patch('openassets.protocol.ColoringEngine.get_output', autospec=True)
    @tests.helpers.async_test
    def test_color_transaction_success(self, get_output_mock, loop):
        get_output_mock.side_effect = lambda _, __, index: self.as_future(self.create_test_outputs()[index - 1], loop)

        target = openassets.protocol.ColoringEngine(None, None, loop)

        # Valid transaction
        outputs = yield from target.color_transaction(self.create_test_transaction(
            b'\x6a\x08' + b'OA\x01\x00' + b'\x02\x05\x07' + b'\00'))

        issuance_asset_id = openassets.protocol.ColoringEngine.hash_script(b'\x10')
        self.assert_output(outputs[0], 10, b'\x10', issuance_asset_id, 5, OutputType.issuance)
        self.assert_output(outputs[1], 20, b'\x6a\x08' + b'OA\x01\x00' + b'\x02\x05\x07' + b'\00',
            None, 0, OutputType.marker_output)
        self.assert_output(outputs[2], 30, b'\x20', b'a', 7, OutputType.transfer)

        # Invalid payload
        outputs = yield from target.color_transaction(self.create_test_transaction(
            b'\x6a\x04' + b'OA\x01\x00'))

        self.assert_output(outputs[0], 10, b'\x10', None, 0, OutputType.uncolored)
        self.assert_output(outputs[1], 20, b'\x6a\x04' + b'OA\x01\x00', None, 0, OutputType.uncolored)
        self.assert_output(outputs[2], 30, b'\x20', None, 0, OutputType.uncolored)

        # Invalid coloring (the asset quantity count is larger than the number of items in the asset quantity list)
        outputs = yield from target.color_transaction(self.create_test_transaction(
            b'\x6a\x08' + b'OA\x01\x00' + b'\x03\x05\x09\x08' + b'\00'))

        self.assert_output(outputs[0], 10, b'\x10', None, 0, OutputType.uncolored)
        self.assert_output(outputs[1], 20, b'\x6a\x08' + b'OA\x01\x00' + b'\x03\x05\x09\x08' + b'\00',
            None, 0, OutputType.uncolored)
        self.assert_output(outputs[2], 30, b'\x20', None, 0, OutputType.uncolored)

    @unittest.mock.patch('openassets.protocol.ColoringEngine.get_output', autospec=True)
    @tests.helpers.async_test
    def test_color_transaction_invalid_marker_outputs(self, get_output_mock, loop):
        get_output_mock.side_effect = lambda _, __, index: self.as_future(self.create_test_outputs()[index - 1], loop)

        target = openassets.protocol.ColoringEngine(None, None, loop)

        transaction = bitcoin.core.CTransaction(
            [
                bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x01' * 32, 1)),
                bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x02' * 32, 2)),
                bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x03' * 32, 3))
            ],
            [
                # If the LEB128-encoded asset quantity of any output exceeds 9 bytes,
                # the marker output is deemed invalid
                bitcoin.core.CTxOut(10, bitcoin.core.CScript(
                    b'\x6a\x10' + b'OA\x01\x00' + b'\x01' + b'\x80\x80\x80\x80\x80\x80\x80\x80\x80\x02' + b'\x00')),
                # If the marker output is malformed, it is considered invalid.
                bitcoin.core.CTxOut(20, bitcoin.core.CScript(
                    b'\x6a\x07' + b'OA\x01\x00' + b'\x01' + b'\x04' + b'\x02')),
                # If there are more items in the asset quantity list than the number of colorable outputs,
                # the marker output is deemed invalid
                bitcoin.core.CTxOut(30, bitcoin.core.CScript(
                    b'\x6a\x0D' + b'OA\x01\x00' + b'\x07' + b'\x01\x01\x01\x01\x01\x01\x01' + b'\x00')),
                # If there are less asset units in the input sequence than in the output sequence,
                # the marker output is considered invalid.
                bitcoin.core.CTxOut(40, bitcoin.core.CScript(
                    b'\x6a\x0B' + b'OA\x01\x00' + b'\x05' + b'\x00\x00\x00\x08\x02' + b'\x00')),
                # If any output contains units from more than one distinct asset ID,
                # the marker output is considered invalid
                bitcoin.core.CTxOut(50, bitcoin.core.CScript(
                    b'\x6a\x0B' + b'OA\x01\x00' + b'\x05' + b'\x00\x00\x00\x00\x09' + b'\x00')),
                # Valid marker output
                bitcoin.core.CTxOut(60, bitcoin.core.CScript(
                    b'\x6a\x0C' + b'OA\x01\x00' + b'\x06' + b'\x01\x01\x01\x01\x01\x08' + b'\x00')),
                bitcoin.core.CTxOut(70, bitcoin.core.CScript(b'\x20'))
            ]
        )

        outputs = yield from target.color_transaction(transaction)

        issuance_asset_id = openassets.protocol.ColoringEngine.hash_script(b'\x10')
        vout = transaction.vout
        self.assert_output(outputs[0], 10, vout[0].scriptPubKey, issuance_asset_id, 1, OutputType.issuance)
        self.assert_output(outputs[1], 20, vout[1].scriptPubKey, issuance_asset_id, 1, OutputType.issuance)
        self.assert_output(outputs[2], 30, vout[2].scriptPubKey, issuance_asset_id, 1, OutputType.issuance)
        self.assert_output(outputs[3], 40, vout[3].scriptPubKey, issuance_asset_id, 1, OutputType.issuance)
        self.assert_output(outputs[4], 50, vout[4].scriptPubKey, issuance_asset_id, 1, OutputType.issuance)
        self.assert_output(outputs[5], 60, vout[5].scriptPubKey, None, 0, OutputType.marker_output)
        self.assert_output(outputs[6], 70, vout[6].scriptPubKey, b'a', 8, OutputType.transfer)

    @unittest.mock.patch('openassets.protocol.ColoringEngine.get_output', autospec=True)
    @tests.helpers.async_test
    def test_color_transaction_coinbase(self, get_output_mock, loop):
        get_output_mock.side_effect = lambda _, __, index: self.as_future(self.create_test_outputs()[index - 1], loop)

        target = openassets.protocol.ColoringEngine(None, None, loop)

        transaction = bitcoin.core.CTransaction(
            [
                bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x00' * 32, 0xffffffff))
            ],
            [
                bitcoin.core.CTxOut(10, bitcoin.core.CScript(b'\x10')),
                bitcoin.core.CTxOut(20, bitcoin.core.CScript(b'\x6a\x07' + b'OA\x01\x00' + b'\x01\x05' + b'\00')),
                bitcoin.core.CTxOut(30, bitcoin.core.CScript(b'\x20'))
            ]
        )

        outputs = yield from target.color_transaction(transaction)

        self.assert_output(outputs[0], 10, transaction.vout[0].scriptPubKey, None, 0, OutputType.uncolored)
        self.assert_output(outputs[1], 20, transaction.vout[1].scriptPubKey, None, 0, OutputType.uncolored)
        self.assert_output(outputs[2], 30, transaction.vout[2].scriptPubKey, None, 0, OutputType.uncolored)

    # _compute_asset_ids

    def test_compute_asset_ids_issuance(self):
        # Issue an asset
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': None, 'asset_quantity': 0, 'output_script': b'abcdef'},
                {'asset_id': None, 'asset_quantity': 0, 'output_script': b'ghijkl'}
            ],
            asset_quantities=[1, 3],
            marker_index=2,
            output_count=3
        )

        issuance_asset_id = openassets.protocol.ColoringEngine.hash_script(b'abcdef')
        self.assert_output(outputs[0], 0, b'0', issuance_asset_id, 1, OutputType.issuance)
        self.assert_output(outputs[1], 1, b'1', issuance_asset_id, 3, OutputType.issuance)
        self.assert_output(outputs[2], 2, b'2', None, 0, OutputType.marker_output)

    def test_compute_asset_ids_transfer(self):
        # No asset quantity defined
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 2}
            ],
            asset_quantities=[],
            output_count=1
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)

        # More asset quantity values than outputs
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 2}
            ],
            asset_quantities=[1],
            output_count=1
        )
        self.assertIsNone(outputs)

        # Single input and single output
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 2}
            ],
            asset_quantities=[2],
            output_count=2
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)
        self.assert_output(outputs[1], 1, b'1', b'a', 2, OutputType.transfer)

        # Empty outputs
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 2}
            ],
            asset_quantities=[0, 1, 0, 1],
            output_count=6
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)
        self.assert_output(outputs[1], 1, b'1', None, 0, OutputType.transfer)
        self.assert_output(outputs[2], 2, b'2', b'a', 1, OutputType.transfer)
        self.assert_output(outputs[3], 3, b'3', None, 0, OutputType.transfer)
        self.assert_output(outputs[4], 4, b'4', b'a', 1, OutputType.transfer)
        self.assert_output(outputs[5], 5, b'5', None, 0, OutputType.transfer)

        # Empty inputs
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': None, 'asset_quantity': 0},
                {'asset_id': b'a', 'asset_quantity': 1},
                {'asset_id': None, 'asset_quantity': 0},
                {'asset_id': b'a', 'asset_quantity': 1},
                {'asset_id': None, 'asset_quantity': 0}
            ],
            asset_quantities=[2],
            output_count=2
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)
        self.assert_output(outputs[1], 1, b'1', b'a', 2, OutputType.transfer)

        # Input partially unassigned
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 1},
                {'asset_id': b'a', 'asset_quantity': 3}
            ],
            asset_quantities=[1, 2],
            output_count=3
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)
        self.assert_output(outputs[1], 1, b'1', b'a', 1, OutputType.transfer)
        self.assert_output(outputs[2], 2, b'2', b'a', 2, OutputType.transfer)

        # Entire input unassigned
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 1},
                {'asset_id': b'a', 'asset_quantity': 3}
            ],
            asset_quantities=[1],
            output_count=3
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)
        self.assert_output(outputs[1], 1, b'1', b'a', 1, OutputType.transfer)
        self.assert_output(outputs[2], 2, b'2', None, 0, OutputType.transfer)

        # Output partially unassigned
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 1},
                {'asset_id': b'a', 'asset_quantity': 2}
            ],
            asset_quantities=[1, 3],
            output_count=3
        )
        self.assertIsNone(outputs)

        # Entire output unassigned
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 1}
            ],
            asset_quantities=[1, 3],
            output_count=3
        )
        self.assertIsNone(outputs)

        # Multiple inputs and outputs - Matching asset quantities
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 1},
                {'asset_id': b'b', 'asset_quantity': 2},
                {'asset_id': b'c', 'asset_quantity': 3}
            ],
            asset_quantities=[1, 2, 3],
            output_count=4
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)
        self.assert_output(outputs[1], 1, b'1', b'a', 1, OutputType.transfer)
        self.assert_output(outputs[2], 2, b'2', b'b', 2, OutputType.transfer)
        self.assert_output(outputs[3], 3, b'3', b'c', 3, OutputType.transfer)

        # Multiple inputs and outputs - Mixing same asset
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 2},
                {'asset_id': b'a', 'asset_quantity': 1},
                {'asset_id': b'a', 'asset_quantity': 2}
            ],
            asset_quantities=[1, 3, 1],
            output_count=4
        )
        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.marker_output)
        self.assert_output(outputs[1], 1, b'1', b'a', 1, OutputType.transfer)
        self.assert_output(outputs[2], 2, b'2', b'a', 3, OutputType.transfer)
        self.assert_output(outputs[3], 3, b'3', b'a', 1, OutputType.transfer)

        # Multiple inputs and outputs - Mixing different assets
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 2},
                {'asset_id': b'b', 'asset_quantity': 1},
                {'asset_id': b'c', 'asset_quantity': 2}
            ],
            asset_quantities=[1, 3, 1],
            output_count=4
        )
        self.assertIsNone(outputs)

    def test_compute_asset_ids_issuance_transfer(self):
        # Transaction mixing both issuance and transfer
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': b'a', 'asset_quantity': 3, 'output_script': b'abcdef'},
                {'asset_id': b'a', 'asset_quantity': 2, 'output_script': b'ghijkl'}
            ],
            asset_quantities=[1, 4, 2, 3],
            marker_index=2,
            output_count=5
        )

        issuance_asset_id = openassets.protocol.ColoringEngine.hash_script(b'abcdef')
        self.assert_output(outputs[0], 0, b'0', issuance_asset_id, 1, OutputType.issuance)
        self.assert_output(outputs[1], 1, b'1', issuance_asset_id, 4, OutputType.issuance)
        self.assert_output(outputs[2], 2, b'2', None, 0, OutputType.marker_output)
        self.assert_output(outputs[3], 3, b'3', b'a', 2, OutputType.transfer)
        self.assert_output(outputs[4], 4, b'4', b'a', 3, OutputType.transfer)

    def test_compute_asset_ids_no_input(self):
        # Transaction with no input
        outputs = self.color_outputs(
            inputs=[],
            asset_quantities=[3],
            marker_index=1,
            output_count=2
        )

        self.assertIsNone(outputs)

    def test_compute_asset_ids_no_asset_quantity(self):
        # Issue an asset
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': None, 'asset_quantity': 0, 'output_script': b'abcdef'},
                {'asset_id': None, 'asset_quantity': 0, 'output_script': b'ghijkl'}
            ],
            asset_quantities=[],
            marker_index=1,
            output_count=3
        )

        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.issuance)
        self.assert_output(outputs[1], 1, b'1', None, 0, OutputType.marker_output)
        self.assert_output(outputs[2], 2, b'2', None, 0, OutputType.transfer)

    def test_compute_asset_ids_zero_asset_quantity(self):
        # Issue an asset
        outputs = self.color_outputs(
            inputs=[
                {'asset_id': None, 'asset_quantity': 0, 'output_script': b'abcdef'},
                {'asset_id': None, 'asset_quantity': 0, 'output_script': b'ghijkl'}
            ],
            asset_quantities=[0],
            marker_index=1,
            output_count=3
        )

        self.assert_output(outputs[0], 0, b'0', None, 0, OutputType.issuance)
        self.assert_output(outputs[1], 1, b'1', None, 0, OutputType.marker_output)
        self.assert_output(outputs[2], 2, b'2', None, 0, OutputType.transfer)

    # hash_script

    def test_hash_script(self):
        previous_output = binascii.unhexlify('76a914010966776006953D5567439E5E39F86A0D273BEE88AC')
        output = openassets.protocol.ColoringEngine.hash_script(previous_output)
        self.assertEqual(binascii.unhexlify('36e0ea8e93eaa0285d641305f4c81e563aa570a2'), output)

    # Test helpers

    def color_outputs(self, inputs, asset_quantities, output_count, marker_index=0):
        previous_outputs = [
            openassets.protocol.TransactionOutput(
                10, bitcoin.core.CScript(item.get('output_script', b'\x01\x02')),
                item['asset_id'],
                item['asset_quantity'],
                None)
            for item in inputs]

        outputs = []
        for i in range(0, output_count):
            outputs.append(bitcoin.core.CTxOut(i, bitcoin.core.CScript(bytes(str(i), encoding='UTF-8'))))

        return openassets.protocol.ColoringEngine._compute_asset_ids(
            previous_outputs,
            marker_index,
            outputs,
            asset_quantities)

    def assert_output(self, output, value, script, asset_id, asset_quantity, output_type):
        self.assertEqual(value, output.value)
        self.assertEqual(script, bytes(output.script))
        self.assertEqual(asset_id, output.asset_id)
        self.assertEqual(asset_quantity, output.asset_quantity)
        self.assertEqual(output_type, output.output_type)

    def create_test_transaction(self, marker_output):
        return bitcoin.core.CTransaction(
            [
                bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x01' * 32, 1)),
                bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x02' * 32, 2)),
                bitcoin.core.CTxIn(bitcoin.core.COutPoint(b'\x03' * 32, 3))
            ],
            [
                bitcoin.core.CTxOut(10, bitcoin.core.CScript(b'\x10')),
                bitcoin.core.CTxOut(20, bitcoin.core.CScript(marker_output)),
                bitcoin.core.CTxOut(30, bitcoin.core.CScript(b'\x20'))
            ]
        )

    def create_test_outputs(self):
        return [
            openassets.protocol.TransactionOutput(1, bitcoin.core.CScript(b'\x10'), b'a', 6, OutputType.issuance),
            openassets.protocol.TransactionOutput(2, bitcoin.core.CScript(b'\x20'), b'a', 2, OutputType.marker_output),
            openassets.protocol.TransactionOutput(3, bitcoin.core.CScript(b'\x30'), b'b', 1, OutputType.transfer)
        ]

    @staticmethod
    def as_future(result, loop):
        future = asyncio.Future(loop=loop)
        future.set_result(result)
        return future


class MarkerOutputTests(unittest.TestCase):
    def test_leb128_encode_decode_success(self):
        def assert_leb128(value, data):
            # Check encoding
            encoded = openassets.protocol.MarkerOutput.leb128_encode(value)
            self.assertEqual(data, encoded)

            # Check decoding
            with io.BytesIO(data) as stream:
                result = openassets.protocol.MarkerOutput.leb128_decode(stream)
                self.assertEqual(value, result)

        assert_leb128(0, b'\x00')
        assert_leb128(1, b'\x01')
        assert_leb128(127, b'\x7F')
        assert_leb128(128, b'\x80\x01')
        assert_leb128(0xff, b'\xff\x01')
        assert_leb128(0x100, b'\x80\x02')
        assert_leb128(300, b'\xac\x02')
        assert_leb128(624485, b'\xe5\x8e\x26')
        assert_leb128(0xffffff, b'\xff\xff\xff\x07')
        assert_leb128(0x1000000, b'\x80\x80\x80\x08')
        assert_leb128(2 ** 64, b'\x80\x80\x80\x80\x80\x80\x80\x80\x80\x02')

    def test_leb128_decode_invalid(self):
        data = b'\xe5\x8e'

        with io.BytesIO(data) as stream:
            self.assertRaises(bitcoin.core.SerializationTruncationError,
                openassets.protocol.MarkerOutput.leb128_decode, stream)

    def test_parse_script_success(self):
        def assert_parse_script(expected, data):
            script = bitcoin.core.CScript(data)
            self.assertEqual(expected, openassets.protocol.MarkerOutput.parse_script(script))

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

    def test_build_script(self):
        def assert_build_script(expected_script, data):
            script = openassets.protocol.MarkerOutput.build_script(data)
            self.assertEqual(expected_script, bytes(script))

        assert_build_script(b'\x6a\00', b'')
        assert_build_script(b'\x6a\05abcde', b'abcde')
        assert_build_script(b'\x6a\x4c\x4c' + (b'a' * 76), b'a' * 76)
        assert_build_script(b'\x6a\x4d\x00\x01' + (b'a' * 256), b'a' * 256)

    def test_serialize_deserialize_payload_success(self):
        def assert_deserialize_payload(asset_quantities, metadata, data):
            # Check serialization
            serialized_output = openassets.protocol.MarkerOutput(asset_quantities, metadata).serialize_payload()
            self.assertEqual(data, serialized_output)

            # Check deserialization
            marker_output = openassets.protocol.MarkerOutput.deserialize_payload(data)
            self.assertEqual(asset_quantities, marker_output.asset_quantities)
            self.assertEqual(metadata, marker_output.metadata)

        assert_deserialize_payload([5, 300], b'abcdef', b'OA\x01\x00' + b'\x02\x05\xac\x02' + b'\06abcdef')
        # Large number of asset quantities
        assert_deserialize_payload([5] * 256, b'abcdef',
            b'OA\x01\x00' + b'\xfd\x00\x01' + (b'\x05' * 256) + b'\06abcdef')
        # Large metadata
        assert_deserialize_payload([5], b'\x01' * 256,
            b'OA\x01\x00' + b'\x01\x05' + b'\xfd\x00\x01' + b'\x01' * 256)
        # Biggest valid output quantity
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

    def test_repr(self):
        target = openassets.protocol.MarkerOutput([5, 100, 0], b'abcd')
        self.assertEqual('MarkerOutput(asset_quantities=[5, 100, 0], metadata=b\'abcd\')', str(target))


class TransactionOutputTests(unittest.TestCase):
    def test_init_success(self):
        target = openassets.protocol.TransactionOutput(
            100, bitcoin.core.CScript(b'abcd'), b'efgh', 2 ** 63 - 1, OutputType.transfer)

        self.assertEqual(100, target.value)
        self.assertEqual(b'abcd', bytes(target.script))
        self.assertEqual(b'efgh', target.asset_id)
        self.assertEqual(2 ** 63 - 1, target.asset_quantity)
        self.assertEqual(OutputType.transfer, target.output_type)

    def test_init_invalid_asset_quantity(self):
        # The asset quantity must be between 0 and 2**63 - 1
        self.assertRaises(AssertionError, openassets.protocol.TransactionOutput,
            100, bitcoin.core.CScript(b'abcd'), b'efgh', 2 ** 63, OutputType.transfer)
        self.assertRaises(AssertionError, openassets.protocol.TransactionOutput,
            100, bitcoin.core.CScript(b'abcd'), b'efgh', -1, OutputType.transfer)

    def test_repr(self):
        target = openassets.protocol.TransactionOutput(
            100, bitcoin.core.CScript(b'abcd'), b'efgh', 1500, OutputType.transfer)

        self.assertEqual('TransactionOutput(' +
            'value=100, ' +
            'script=CScript([OP_NOP, OP_VER, OP_IF, OP_NOTIF]), ' +
            'asset_id=b\'efgh\', ' +
            'asset_quantity=1500, ' +
            'output_type=<OutputType.transfer: 3>)',
            str(target))

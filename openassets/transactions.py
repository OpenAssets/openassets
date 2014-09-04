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

"""
Provides functions for constructing unsigned Open Assets transactions.
"""

import bitcoin.core
import openassets.protocol


class TransactionBuilder(object):
    """Provides methods for constructing Open Assets transactions."""

    def __init__(self, dust_amount):
        """
        Initializes a new instance of the TransactionBuilder class.

        :param int dust_amount: The minimum allowed output value.
        """
        self._dust_amount = dust_amount

    def issue(self, unspent_outputs, from_script, to_script, change_script, asset_quantity, metadata, fees):
        """
        Creates a transaction for issuing an asset.

        :param list[SpendableOutput] unspent_outputs: A list of unspent outputs.
        :param bytes from_script: The script from which the coins are issued. This determines the asset address.
        :param bytes to_script: The script where the issued coins are sent.
        :param bytes change_script: The script where uncolored change is sent.
        :param int asset_quantity: The number of units to be issued.
        :param bytes metadata: The metadata to be embedded in the transaction.
        :param int fees: The fees to include in the transaction.
        :return: An unsigned transaction for issuing an asset.
        :rtype: CTransaction
        """
        inputs, total_amount = self._collect_uncolored_outputs(
            unspent_outputs, from_script, 2 * self._dust_amount + fees)

        return bitcoin.core.CTransaction(
            vin=[bitcoin.core.CTxIn(item.out_point, item.output.scriptPubKey) for item in inputs],
            vout=[
                self._get_colored_output(to_script),
                self._get_marker_output([asset_quantity], metadata),
                self._get_uncolored_output(change_script, total_amount - self._dust_amount - fees)
            ]
        )

    def transfer(self, unspent_outputs, transfer_spec, from_btc, to_btc, amount_btc, fees):
        """
        Creates a transaction for sending assets and bitcoins.

        :param list[SpendableOutput] unspent_outputs: A list of unspent outputs.
        :param list[(bytes, bytes, bytes, int)] transfer_spec: A list of tuples. In each tuple:
            - The first element is the spending script.
            - The second element is the receiving script.
            - The third element is the asset address of the asset being sent.
            - The fourth element is the number of asset units being sent.
        :param bytes from_btc: The script from which to pay bitcoins.
        :param bytes to_btc: The script receiving the bitcoin payment.
        :param int amount_btc: The amount of satoshis to send.
        :param int fees: The fees to include in the transaction.
        :return: An unsigned transaction for sending assets and bitcoins.
        :rtype: CTransaction
        """
        inputs = []
        outputs = []
        asset_quantities = []
        for color_send in transfer_spec:
            asset_quantity = color_send[3]
            asset_address = color_send[2]
            colored_outputs, collected_amount = self._collect_colored_outputs(
                unspent_outputs, color_send[0], asset_address, asset_quantity)
            inputs.extend(colored_outputs)
            outputs.append(self._get_colored_output(color_send[1]))
            asset_quantities.append(asset_quantity)

            if collected_amount > asset_quantity:
                outputs.append(self._get_colored_output(color_send[0]))
                asset_quantities.append(collected_amount - asset_quantity)

        btc_excess = sum([input.output.nValue for input in inputs]) - sum([output.nValue for output in outputs])

        if btc_excess < amount_btc + fees:
            # Not enough bitcoin inputs
            uncolored_outputs, total_amount = self._collect_uncolored_outputs(
                unspent_outputs, from_btc, amount_btc + fees - btc_excess)
            inputs.extend(uncolored_outputs)
            btc_excess += total_amount

        if btc_excess > amount_btc + fees:
            # Too much bitcoin in input, send it back as change
            outputs.append(self._get_uncolored_output(from_btc, btc_excess - amount_btc - fees))

        if amount_btc > 0:
            outputs.append(self._get_uncolored_output(to_btc, amount_btc))

        if asset_quantities:
            outputs.insert(0, self._get_marker_output(asset_quantities, b''))

        return bitcoin.core.CTransaction(
            vin=[bitcoin.core.CTxIn(item.out_point, item.output.scriptPubKey) for item in inputs],
            vout=outputs
        )

    def transfer_bitcoin(self, unspent_outputs, from_script, to_script, amount_btc, fees):
        """
        Creates a transaction for sending bitcoins.

        :param list[SpendableOutput] unspent_outputs: A list of unspent outputs.
        :param bytes from_script: The script from which to pay bitcoins.
        :param bytes to_script: The script receiving the bitcoin payment.
        :param int amount_btc: The amount of satoshis to send.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        return self.transfer(unspent_outputs, [], from_script, to_script, amount_btc, fees)

    def transfer_assets(self, unspent_outputs, from_script, to_script, asset_address, asset_quantity, fees):
        """
        Creates a transaction for sending an asset.

        :param list[SpendableOutput] unspent_outputs: A list of unspent outputs.
        :param bytes from_script: The script from which to send assets.
        :param bytes to_script: The script receiving the payment.
        :param bytes asset_address: The address of the asset being sent.
        :param int asset_quantity: The number of units being sent.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        return self.transfer(
            unspent_outputs,
            [(from_script, to_script, asset_address, asset_quantity)],
            from_script, to_script, 0, fees)

    def btc_asset_swap(
            self, unspent_outputs, asset_from_script, btc_from_script, asset_address, asset_quantity, amount_btc, fees):
        """
        Creates a transaction for swapping assets for bitcoins.

        :param list[SpendableOutput] unspent_outputs: A list of unspent outputs.
        :param bytes asset_from_script: The script from which to send assets, and receiving the bitcoins.
        :param bytes btc_from_script: The script from which to send bitcoins, and receiving the assets.
        :param bytes asset_address: The address of the asset being sent.
        :param int asset_quantity: The number of units being sent.
        :param int amount_btc: The amount of satoshis to send.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        return self.transfer(
            unspent_outputs,
            [(asset_from_script, btc_from_script, asset_address, asset_quantity)],
            btc_from_script, asset_from_script, amount_btc, fees)

    def asset_asset_swap(
            self, unspent_outputs, asset1_from_script, asset2_from_script, asset1_address, asset1_quantity,
            asset2_address, asset2_quantity, fees):
        """
        Creates a transaction for swapping an asset for another asset.

        :param list[SpendableOutput] unspent_outputs: A list of unspent outputs.
        :param bytes asset1_from_script: The script from which to send the first asset, and receiving the second asset.
            It also pays for fees and/or receives change if any.
        :param bytes asset2_from_script: The script from which to send the second asset, and receiving the first asset.
        :param bytes asset1_address: The address of the first asset.
        :param int asset1_quantity: The number of units of the first asset being sent.
        :param bytes asset2_address: The address of the second asset.
        :param int asset2_quantity: The number of units of the second asset being sent.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        return self.transfer(
            unspent_outputs,
            [
                (asset1_from_script, asset2_from_script, asset1_address, asset1_quantity),
                (asset2_from_script, asset1_from_script, asset2_address, asset2_quantity)
            ],
            asset1_from_script, asset1_from_script, 0, fees)

    @staticmethod
    def _collect_uncolored_outputs(unspent_outputs, from_script, amount):
        """
        Returns a list of uncolored outputs for the specified amount.

        :param list[SpendableOutput] unspent_outputs: The list of available outputs.
        :param bytes from_script: The source script to collect outputs from.
        :param int amount: The amount to collect.
        :return: A list of outputs, and the total amount collected.
        :rtype: (list[SpendableOutput], int)
        """
        total_amount = 0
        result = []
        for output in unspent_outputs:
            if output.output.asset_address is None and bytes(output.output.scriptPubKey) == from_script:
                result.append(output)
                total_amount += output.output.nValue

            if total_amount >= amount:
                return result, total_amount

        raise InsufficientFundsError

    @staticmethod
    def _collect_colored_outputs(unspent_outputs, from_script, asset_address, asset_quantity):
        """
        Returns a list of colored outputs for the specified quantity.

        :param list[SpendableOutput] unspent_outputs: The list of available outputs.
        :param bytes from_script: The source script to collect outputs from.
        :param bytes asset_address: The address of the asset to collect.
        :param int asset_quantity: The asset quantity to collect.
        :return: A list of outputs, and the total asset quantity collected.
        :rtype: (list[SpendableOutput], int)
        """
        total_amount = 0
        result = []
        for output in unspent_outputs:
            if output.output.asset_address == asset_address and bytes(output.output.scriptPubKey) == from_script:
                result.append(output)
                total_amount += output.output.asset_quantity

            if total_amount >= asset_quantity:
                return result, total_amount

        raise InsufficientAssetQuantityError

    def _get_uncolored_output(self, script, value):
        """
        Creates an uncolored output.

        :param bytes script: The output script.
        :param int value: The satoshi value of the output.
        :return: An object representing the uncolored output.
        :rtype: TransactionOutput
        """
        if value < self._dust_amount:
            raise DustOutputError

        return bitcoin.core.CTxOut(value, bitcoin.core.CScript(script))

    def _get_colored_output(self, script):
        """
        Creates a colored output.

        :param bytes script: The output script.
        :return: An object representing the colored output.
        :rtype: TransactionOutput
        """
        return bitcoin.core.CTxOut(self._dust_amount, bitcoin.core.CScript(script))

    def _get_marker_output(self, asset_quantities, metadata):
        """
        Creates a marker output.

        :param list[int] asset_quantities: The asset quantity list.
        :param bytes metadata: The metadata contained in the output.
        :return: An object representing the marker output.
        :rtype: TransactionOutput
        """
        payload = openassets.protocol.MarkerOutput(asset_quantities, metadata).serialize_payload()
        script = openassets.protocol.MarkerOutput.build_script(payload)
        return bitcoin.core.CTxOut(0, script)


class SpendableOutput(object):
    """Represents a transaction output with information about the asset address and asset quantity associated to it."""

    def __init__(self, out_point, output):
        """
        Initializes a new instance of the TransactionOutput class.

        :param COutPoint out_point: An object that can be used to locate the output.
        :param TransactionOutput output: The actual output object.
        """
        self._out_point = out_point
        self._output = output

    @property
    def out_point(self):
        """
        Gets an object that can be used to locate the output.

        :return: An object that can be used to locate the output.
        :rtype: COutPoint
        """
        return self._out_point

    @property
    def output(self):
        """
        Gets the output object.

        :return: The actual output object.
        :rtype: TransactionOutput
        """
        return self._output


class TransactionBuilderError(Exception):
    """The transaction could not be built."""
    pass


class InsufficientFundsError(TransactionBuilderError):
    """An insufficient amount of bitcoins is available."""
    pass


class InsufficientAssetQuantityError(TransactionBuilderError):
    """An insufficient amount of assets is available."""
    pass


class DustOutputError(TransactionBuilderError):
    """The value of an output would be too small, and the output would be considered as dust."""
    pass
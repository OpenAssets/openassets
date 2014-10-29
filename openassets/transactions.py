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

    def issue(self, issuance_spec, metadata, fees):
        """
        Creates a transaction for issuing an asset.

        :param TransferParameters issuance_spec: The parameters of the issuance.
        :param bytes metadata: The metadata to be embedded in the transaction.
        :param int fees: The fees to include in the transaction.
        :return: An unsigned transaction for issuing an asset.
        :rtype: CTransaction
        """
        inputs, total_amount = self._collect_uncolored_outputs(
            issuance_spec.unspent_outputs, 2 * self._dust_amount + fees)

        return bitcoin.core.CTransaction(
            vin=[bitcoin.core.CTxIn(item.out_point, item.output.script) for item in inputs],
            vout=[
                self._get_colored_output(issuance_spec.to_script),
                self._get_marker_output([issuance_spec.amount], metadata),
                self._get_uncolored_output(issuance_spec.change_script, total_amount - self._dust_amount - fees)
            ]
        )

    def transfer(self, asset_transfer_specs, btc_transfer_spec, fees):
        """
        Creates a transaction for sending assets and bitcoins.

        :param list[(bytes, TransferParameters)] asset_transfer_specs: A list of tuples. In each tuple:
            - The first element is the ID of an asset.
            - The second element is the parameters of the transfer.
        :param TransferParameters btc_transfer_spec: The parameters of the bitcoins being transferred.
        :param int fees: The fees to include in the transaction.
        :return: An unsigned transaction for sending assets and bitcoins.
        :rtype: CTransaction
        """
        inputs = []
        outputs = []
        asset_quantities = []
        for asset_id, transfer_spec in asset_transfer_specs:
            colored_outputs, collected_amount = self._collect_colored_outputs(
                transfer_spec.unspent_outputs, asset_id, transfer_spec.amount)
            inputs.extend(colored_outputs)
            outputs.append(self._get_colored_output(transfer_spec.to_script))
            asset_quantities.append(transfer_spec.amount)

            if collected_amount > transfer_spec.amount:
                outputs.append(self._get_colored_output(transfer_spec.change_script))
                asset_quantities.append(collected_amount - transfer_spec.amount)

        btc_excess = sum([input.output.value for input in inputs]) - sum([output.nValue for output in outputs])

        if btc_excess < btc_transfer_spec.amount + fees:
            # Not enough bitcoin inputs
            uncolored_outputs, total_amount = self._collect_uncolored_outputs(
                btc_transfer_spec.unspent_outputs, btc_transfer_spec.amount + fees - btc_excess)
            inputs.extend(uncolored_outputs)
            btc_excess += total_amount

        change = btc_excess - btc_transfer_spec.amount - fees
        if change > 0:
            # Too much bitcoin in input, send it back as change
            outputs.append(self._get_uncolored_output(btc_transfer_spec.change_script, change))

        if btc_transfer_spec.amount > 0:
            outputs.append(self._get_uncolored_output(btc_transfer_spec.to_script, btc_transfer_spec.amount))

        if asset_quantities:
            outputs.insert(0, self._get_marker_output(asset_quantities, b''))

        return bitcoin.core.CTransaction(
            vin=[bitcoin.core.CTxIn(item.out_point, item.output.script) for item in inputs],
            vout=outputs
        )

    def transfer_bitcoin(self, transfer_spec, fees):
        """
        Creates a transaction for sending bitcoins.

        :param TransferParameters transfer_spec: The parameters of the bitcoins being transferred.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        return self.transfer([], transfer_spec, fees)

    def transfer_assets(self, asset_id, transfer_spec, btc_change_script, fees):
        """
        Creates a transaction for sending an asset.

        :param bytes asset_id: The ID of the asset being sent.
        :param TransferParameters transfer_spec: The parameters of the asset being transferred.
        :param bytes btc_change_script: The script where to send bitcoin change, if any.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        return self.transfer(
            [(asset_id, transfer_spec)],
            TransferParameters(transfer_spec.unspent_outputs, None, btc_change_script, 0),
            fees)

    def btc_asset_swap(self, btc_transfer_spec, asset_id, asset_transfer_spec, fees):
        """
        Creates a transaction for swapping assets for bitcoins.

        :param TransferParameters btc_transfer_spec: The parameters of the bitcoins being transferred.
        :param bytes asset_id: The ID of the asset being sent.
        :param TransferParameters asset_transfer_spec: The parameters of the asset being transferred.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        return self.transfer([(asset_id, asset_transfer_spec)], btc_transfer_spec, fees)

    def asset_asset_swap(
            self, asset1_id, asset1_transfer_spec, asset2_id, asset2_transfer_spec, fees):
        """
        Creates a transaction for swapping an asset for another asset.

        :param bytes asset1_id: The ID of the first asset.
        :param TransferParameters asset1_transfer_spec: The parameters of the first asset being transferred.
            It is also used for paying fees and/or receiving change if any.
        :param bytes asset2_id: The ID of the second asset.
        :param TransferDetails asset2_transfer_spec: The parameters of the second asset being transferred.
        :param int fees: The fees to include in the transaction.
        :return: The resulting unsigned transaction.
        :rtype: CTransaction
        """
        btc_transfer_spec = TransferParameters(
            asset1_transfer_spec.unspent_outputs, asset1_transfer_spec.to_script, asset1_transfer_spec.change_script, 0)

        return self.transfer(
            [(asset1_id, asset1_transfer_spec), (asset2_id, asset2_transfer_spec)], btc_transfer_spec, fees)

    @staticmethod
    def _collect_uncolored_outputs(unspent_outputs, amount):
        """
        Returns a list of uncolored outputs for the specified amount.

        :param list[SpendableOutput] unspent_outputs: The list of available outputs.
        :param int amount: The amount to collect.
        :return: A list of outputs, and the total amount collected.
        :rtype: (list[SpendableOutput], int)
        """
        total_amount = 0
        result = []
        for output in unspent_outputs:
            if output.output.asset_id is None:
                result.append(output)
                total_amount += output.output.value

            if total_amount >= amount:
                return result, total_amount

        raise InsufficientFundsError

    @staticmethod
    def _collect_colored_outputs(unspent_outputs, asset_id, asset_quantity):
        """
        Returns a list of colored outputs for the specified quantity.

        :param list[SpendableOutput] unspent_outputs: The list of available outputs.
        :param bytes asset_id: The ID of the asset to collect.
        :param int asset_quantity: The asset quantity to collect.
        :return: A list of outputs, and the total asset quantity collected.
        :rtype: (list[SpendableOutput], int)
        """
        total_amount = 0
        result = []
        for output in unspent_outputs:
            if output.output.asset_id == asset_id:
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
    """Represents a transaction output with information about the asset ID and asset quantity associated to it."""

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


class TransferParameters(object):
    """Encapsulates the details of a bitcoin or asset transfer."""

    def __init__(self, unspent_outputs, to_script, change_script, amount):
        """
        Initializes an instance of the TransferParameters class.

        :param list[SpendableOutput] unspent_outputs: The unspent outputs available for the transaction.
        :param bytes to_script: The output script to which to send the assets or bitcoins.
        :param bytes change_script: The output script to which to send any remaining change.
        :param int amount: The asset quantity or amount of satoshis sent in the transaction.
        """
        self._unspent_outputs = unspent_outputs
        self._to_script = to_script
        self._change_script = change_script
        self._amount = amount

    @property
    def unspent_outputs(self):
        """
        Gets the unspent outputs available for the transaction.

        :return: The list of unspent outputs.
        :rtype: list[SpendableOutput]
        """
        return self._unspent_outputs

    @property
    def to_script(self):
        """
        Gets the output script to which to send the assets or bitcoins.

        :return: The output script.
        :rtype: bytes
        """
        return self._to_script

    @property
    def change_script(self):
        """
        Gets the output script to which to send any remaining change.

        :return: The output script.
        :rtype: bytes
        """
        return self._change_script

    @property
    def amount(self):
        """
        Gets either the asset quantity or amount of satoshis sent in the transaction.

        :return: The asset quantity or amount of satoshis.
        :rtype: int
        """
        return self._amount


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
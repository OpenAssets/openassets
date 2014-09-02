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
import bitcoin.core.script
import enum
import hashlib
import io


class ColoringEngine(object):
    """The backtracking engine used to find the asset address and asset quantity of any output."""

    def __init__(self, transaction_provider, cache):
        """
        Constructs an instance of the ColorEngine class.

        :param bytes -> CTransaction transaction_provider: A function returning a transaction given its hash.
        :param OutputCache cache: The cache object to use.
        """
        self._transaction_provider = transaction_provider
        self._cache = cache

    def get_output(self, transaction_hash, output_index):
        """
        Gets an output and information about its asset address and quantity.

        :param bytes transaction_hash: The hash of the transaction containing the output.
        :param int output_index: The index of the output.
        :return: An object containing the output and the asset address and quantity.
        :rtype: TransactionOutput
        """
        cached_output = self._cache.get_output(transaction_hash, output_index)

        if cached_output is not None:
            return cached_output

        transaction = self._transaction_provider(transaction_hash)

        if transaction is None:
            return None

        colored_outputs = self.color_transaction(transaction)

        for output in colored_outputs:
            self._cache.set_output(output)

        return colored_outputs[output_index]

    def color_transaction(self, transaction):
        """
        Computes the asset address and quantity of every output in the transaction.

        :param CTransaction transaction: The transaction to color.
        :return: A list containing all the colored outputs of the transaction.
        :rtype: list[TransactionOutput]
        """
        for i, output in enumerate(transaction.vout):
            marker_output_payload = MarkerOutput.parse_script(output.scriptPubKey)

            if marker_output_payload is not None:
                marker_output = MarkerOutput.deserialize_payload(marker_output_payload)

                if marker_output is not None:

                    # Fetch the colored outputs for previous transactions
                    inputs = [self.get_output(item.prevout.hash, item.prevout.n) for item in transaction.vin]

                    asset_addresses = self._compute_asset_addresses(
                        inputs,
                        i,
                        transaction.vout,
                        marker_output.asset_quantities)

                    if asset_addresses is not None:
                        return asset_addresses

        return [TransactionOutput(output, None, 0, OutputType.uncolored) for output in transaction.vout]

    @classmethod
    def _compute_asset_addresses(cls, inputs, marker_output_index, outputs, asset_quantities):
        """
        Computes the asset addresses of every output in a transaction.

        :param list[TransactionOutput] inputs: The outputs referenced by the inputs of the transaction.
        :param int marker_output_index: The position of the marker output in the transaction.
        :param list[CTxOut] outputs: The outputs of the transaction.
        :param list[int] asset_quantities: The list of asset quantities of the outputs.
        :return: A list of outputs with asset address and quantity information.
        :rtype: list[TransactionOutput]
        """
        # If there are more items in the asset quantities list than outputs in the transaction (excluding the
        # marker output), the transaction is considered invalid
        if len(asset_quantities) > len(outputs) - 1:
            return None

        result = []

        # Add the issuance outputs
        issuance_address = cls.hash_script(bytes(inputs[0].output.scriptPubKey))

        for i in range(0, marker_output_index):
            result.append(TransactionOutput(outputs[i], issuance_address, asset_quantities[i], OutputType.issuance))

        # Add the marker output
        result.append(TransactionOutput(outputs[marker_output_index], None, 0, OutputType.marker_output))

        # Add the transfer outputs
        input_iterator = iter(inputs)
        input_units_left = 0
        for i in range(marker_output_index + 1, len(outputs)):
            if i <= len(asset_quantities):
                output_asset_quantity = asset_quantities[i - 1]
            else:
                output_asset_quantity = 0

            output_units_left = output_asset_quantity
            asset_address = None

            while output_units_left > 0:

                # Move to the next input if the current one is depleted
                if input_units_left == 0:
                    current_input = next(input_iterator, None)
                    if current_input is None:
                        # There are less asset units available in the input than in the outputs:
                        # the transaction is considered invalid
                        return None
                    else:
                        input_units_left = current_input.asset_quantity

                # If the current input is colored, assign its asset address to the current output
                if current_input.asset_address is not None:
                    progress = min(input_units_left, output_units_left)
                    output_units_left -= progress
                    input_units_left -= progress

                    if asset_address is None:
                        # This is the first input to map to this output
                        asset_address = current_input.asset_address
                    elif asset_address != current_input.asset_address:
                        # Another different asset address has already been assigned to that output:
                        # the transaction is considered invalid
                        return None

            result.append(TransactionOutput(outputs[i], asset_address, output_asset_quantity, OutputType.transfer))

        return result

    @classmethod
    def hash_script(cls, data):
        """
        Hash a script into a pay-to-script-hash address using SHA256 followed by RIPEMD160.

        :param bytes data: The data to hash.
        """
        sha256 = hashlib.sha256()
        ripemd = hashlib.new('ripemd160')

        sha256.update(data)
        ripemd.update(sha256.digest())
        return ripemd.digest()


class TransactionOutput(object):
    """Represents a transaction output with information about the asset address and asset quantity associated to it."""

    output = property(lambda self: self._output)
    asset_address = property(lambda self: self._asset_address)
    asset_quantity = property(lambda self: self._asset_quantity)
    output_type = property(lambda self: self._output_type)

    def __init__(self, output, asset_address, asset_quantity, output_type):
        """
        Initializes a new instance of the TransactionOutput class.

        :param CTxOut output: The output object.
        :param bytes asset_address: The asset address of the output.
        :param int asset_quantity: The asset quantity of the output.
        :param OutputType output_type: The type of output.
        """
        self._output = output
        self._asset_address = asset_address
        self._asset_quantity = asset_quantity
        self._output_type = output_type

    def __repr__(self):
        return "TransactionOutput(%r, %r, %r, %r)" % (self.output, self.asset_address, self.asset_quantity, self.output_type)


class OutputType(enum.Enum):
    uncolored = 0
    marker_output = 1
    issuance = 2
    transfer = 3


class OutputCache(object):
    """Represents an interface for an object capable of storing the result of output coloring."""

    def get_output(self, transaction_hash, output_index):
        """
        Returns a cached output.

        :param bytes transaction_hash: The hash of the transaction parent of the output.
        :param int output_index: The index of the output in the transaction.
        :return: The output for the transaction hash and output index provided if it is found in the cache, or None
            otherwise.
        :rtype: TransactionOutput
        """
        return None

    def set_output(self, output):
        """
        Saves an output in cache.

        :param TransactionOutput output: The output to save.
        """
        pass


class MarkerOutput(object):
    """Represents an Open Assets marker output."""

    MAX_ASSET_QUANTITY = 2**63 - 1

    asset_quantities = property(lambda self: self._asset_quantities)
    metadata = property(lambda self: self._metadata)

    def __init__(self, asset_quantities, metadata):
        """
        Initializes a new instance of the MarkerOutputPayload class.

        :param list[int] asset_quantities: The list of asset quantities.
        :param bytes metadata: The metadata in the marker output.
        """
        self._asset_quantities = asset_quantities
        self._metadata = metadata

    @classmethod
    def deserialize_payload(cls, payload):
        """
        Deserializes the Open Assets marker output payload.

        :param bytes payload: A buffer containing the marker output payload.
        :return: The marker output object.
        :rtype: MarkerOutput
        """
        with io.BytesIO(payload) as stream:

            # The OAP marker and protocol version
            oa_version = stream.read(4)
            if oa_version != b'OA\x01\x00':
                return None

            try:
                # A var-integer representing the number of items in the  asset quantity list  field
                output_count = bitcoin.core.VarIntSerializer.stream_deserialize(stream)

                # LEB128-encoded unsigned integers representing the asset quantity of every output in order
                asset_quantities = []
                for i in range(0, output_count):
                    asset_quantity = MarkerOutput.leb128_decode(stream)

                    if asset_quantity > cls.MAX_ASSET_QUANTITY:
                        return None

                    asset_quantities.append(asset_quantity)

                # The var-integer encoded length of the  metadata field.
                metadata_length = bitcoin.core.VarIntSerializer.stream_deserialize(stream)

                # The actual metadata
                metadata = stream.read(metadata_length)

                # If the metadata string wasn't long enough, the marker output is malformed
                if len(metadata) != metadata_length:
                    return None

                # If there are bytes left to read, the marker output is malformed
                last_byte = stream.read(1)
                if len(last_byte) > 0:
                    return None

            except bitcoin.core.SerializationTruncationError:
                return None

            return MarkerOutput(asset_quantities, metadata)

    @classmethod
    def parse_script(cls, output_script):
        """
        Parses an output and returns the payload if the output fits the right pattern for an open assets
        marker output, or None otherwise.

        :param CScript output_script: The output script to be parsed.
        :return: The marker output payload if the output fits the pattern, None otherwise.
        :rtype: bytes
        """
        script_iterator = output_script.raw_iter()

        try:
            first_opcode, _, _ = next(script_iterator, (None, None, None))
            _, data, _ = next(script_iterator, (None, None, None))
            remainder = next(script_iterator, None)
        except bitcoin.core.script.CScriptTruncatedPushDataError:
            return None
        except bitcoin.core.script.CScriptInvalidError:
            return None

        if first_opcode == bitcoin.core.script.OP_RETURN and data is not None and remainder is None:
            return data
        else:
            return None

    @classmethod
    def leb128_decode(cls, data):
        """
        Decodes a LEB128-encoded unsigned integer.

        :param BytesIO data:
        :return: The integer represented in LEB128.
        :rtype: int
        """
        result = 0
        shift = 0

        while True:
            character = data.read(1)
            if len(character) == 0:
                raise bitcoin.core.SerializationTruncationError("Invalid LEB128 integer")

            b = ord(character)
            result |= (b & 0x7f) << shift
            if b & 0x80 == 0:
                break
            shift += 7
        return result

    def __repr__(self):
        return "MarkerOutputPayload(asset_quantities = %r, metadata = %r)" % (self.asset_quantities, self.metadata)

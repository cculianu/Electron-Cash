#!/usr/bin/env python3
#
# Electron Cash - lightweight Bitcoin Cash client
# Copyright (C) 2025 The Electron Cash Developers
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Implementation of PSBT -- Partially Signed Bitcoin Transaction"""

import binascii
import warnings
from typing import Dict, List, Tuple, Optional, Union

from . import bitcoin
from .bitcoin_types import CMutableTransaction, CTxOut
from .serialize import BCDataStream, SerializationError

# PSBT magic bytes
PSBT_MAGIC_BYTES = b'psbt\xff'

# PSBT global types
PSBT_GLOBAL_UNSIGNED_TX = 0x00

# PSBT input types
PSBT_IN_UTXO = 0x00
PSBT_IN_PARTIAL_SIG = 0x02
PSBT_IN_SIGHASH = 0x03
PSBT_IN_REDEEMSCRIPT = 0x04
PSBT_IN_BIP32_DERIVATION = 0x06
PSBT_IN_SCRIPTSIG = 0x07

# PSBT output types
PSBT_OUT_REDEEMSCRIPT = 0x00
PSBT_OUT_BIP32_DERIVATION = 0x02

# The separator is 0x00. Reading this in means that the unserializer can
# interpret it as a 0 length key which indicates that this is the separator.
# The separator has no value.
PSBT_SEPARATOR = b''


class PSBTSerializationError(SerializationError):
    def __init__(self, *args):
        if args and isinstance(args[0], str):
            args = list(args)
            args[0] = "PSBT: " + args[0]
        super().__init__(*args)


class PSBTMagicBytesError(PSBTSerializationError):
    pass


class KeyOriginInfo:
    """A type used by PSBTInput and PSBTOutput"""
    fingerprint: bytes
    path: List[int]

    def __init__(self):
        self.fingerprint = b'\x00\x00\x00\x00'
        self.path = []

    def __repr__(self):
        return f"<KeyOriginInfo fingerprint={self.fingerprint.hex()} path={self.path_str}>"

    def __eq__(self, other):
        return isinstance(other, KeyOriginInfo) and (self.fingerprint, self.path) == (other.fingerprint, other.path)

    @property
    def path_str(self):
        """returns the keypath of the form m/145/1'/0, etc"""
        s = "m"
        for num in self.path:
            if num & 0x80000000:
                hardened = "'"
                num &= ~0x80000000
            else:
                hardened = ""
            s += f"/{num}{hardened}"
        return s


def _deserialize_unknown(vds: BCDataStream, key: bytes, unknown: Dict[bytes, bytes]):
    """Internally used to read "unknown" data from PSBT serialized data"""
    if key in unknown:
        raise PSBTSerializationError("Duplicate Key, key for unknown value already provided")
    val = vds.read_bytes(strict=True)
    unknown[key] = val


def _serialize_unknown(vds: BCDataStream, unknown: Dict[bytes, bytes]):
    for key, val in unknown.items():
        vds.write_string(key)
        vds.write_string(val)


def _validate_pubkey(pubkey: bytes, *, extra_msg=''):
    try:
        bitcoin.ser_to_point(pubkey)
    except Exception as e:
        raise PSBTSerializationError("Invalid pubkey" + extra_msg) from e


def _parse_pubkey(psbt_key: bytes) -> bytes:
    """Ensures the pubkey bytes from a PSBT "psbt_key" are correct and returns the trailing part (after the type
     byte)."""
    if len(psbt_key) != 66 and len(psbt_key) != 34:  # Make sure that the key is the size of pubkey + 1
        raise PSBTSerializationError("Size of key was not the expected size for the type partial signature pubkey")
    pubkey = bytes(psbt_key[1:])
    _validate_pubkey(pubkey)
    return pubkey


def _deserialize_hd_keypath(vds: BCDataStream, psbt_key: bytes, hd_keypaths: dict):
    # Strip first byte off the psbt_key to get to the pubkey, and check its sanity
    pubkey = _parse_pubkey(psbt_key)
    if pubkey in hd_keypaths:
        raise PSBTSerializationError("Duplicate Key, pubkey derivation path already provided")
    # Deserialize the value payload vector, and deserialize that as a series of uint32's
    value = vds.read_bytes(strict=True)
    value_len = len(value)
    if value_len <= 0 or value_len % 4 != 0:
        raise PSBTSerializationError("Invalid length for HD key path")
    vds2 = BCDataStream(value)
    keypath = KeyOriginInfo()
    keypath.fingerprint = vds2.read_bytes(4, strict=True)
    while vds2.can_read_more():
        index = vds2.read_uint32()
        keypath.path.append(index)
    assert value_len == (len(keypath.path) + 1) * 4  # Sanity check
    # Add to map
    hd_keypaths[pubkey] = keypath


def _serialize_hd_keypaths(vds: BCDataStream, hd_keypaths: dict, typ: int):
    for pubkey, keypath in hd_keypaths.items():
        _validate_pubkey(pubkey, extra_msg=" being serialized")
        vds.write_string(bytes((typ,)) + pubkey)  # serialize to vector
        # Serialize fingerprint (4 bytes) + all the uint32's for the path to a vector
        vds2 = BCDataStream()
        if len(keypath.fingerprint) != 4:
            raise PSBTSerializationError("Expected fingerprint length of 4")
        vds2.write(keypath.fingerprint)
        for path in keypath.path:
            vds2.write_uint32(path)
        # Then serialize this as a vector to the stream
        vds.write_string(vds2.input)


class _PSBTInputOutputBase:
    redeem_script: bytes  # Always raw bytes, never hex
    hd_keypaths: Dict[bytes, KeyOriginInfo]  # Map of pubkey -> KeyOriginInfo
    unknown: Dict[bytes, bytes]  # Map of key, value for unknown byte blob data

    def __init__(self):
        self._clear()

    def _clear(self):
        self.redeem_script = b''
        self.hd_keypaths = {}
        self.unknown = {}

    def _base_rep_str(self):
        hkp_str = ", ".join(f"({pk.hex()}, {koi!r})" for pk, koi in self.hd_keypaths.items())
        unk_str = ", ".join(f"({key.hex()}, {val.hex()})" for key, val in self.unknown.items())
        return f"redeem_script={self.redeem_script.hex()} hd_keypaths=[{hkp_str}] unknown=[{unk_str}]"

    def __eq__(self, other):
        return isinstance(other, _PSBTInputOutputBase) and (
            (self.redeem_script, self.hd_keypaths, self.unknown) ==
            (other.redeem_script, other.hd_keypaths, other.unknown)
        )


class PSBTInput(_PSBTInputOutputBase):
    utxo: Optional[CTxOut]
    final_script_sig: bytes  # Always raw bytes, never hex
    partial_sigs: Dict[bytes, Tuple[bytes, bytes]]  # Map of hash160 -> tuple(pubkey, sig)
    sighash_type: int  # 0x40, 0x41, etc

    def __init__(self):
        super().__init__()
        self._clear(derived_attributes_only=True)

    def _clear(self, *, derived_attributes_only=False):
        if not derived_attributes_only:
            super()._clear()
        self.utxo = None
        self.final_script_sig = b''
        self.partial_sigs = {}
        self.sighash_type = 0

    def __repr__(self):
        ps_str = ", ".join(f"({k.hex()}, ({tup[0].hex()}, {tup[1].hex()}))" for k, tup in self.partial_sigs.items())
        return f"<PSBTInput utxo={self.utxo!r} final_script_sig={self.final_script_sig.hex()} partial_sigs=[{ps_str}]" \
               f" sighash_type={self.sighash_type}, {self._base_rep_str()}>"

    def __eq__(self, other):
        return isinstance(other, PSBTInput) and super().__eq__(other) and (
            (self.utxo, self.final_script_sig, self.partial_sigs, self.sighash_type) ==
            (other.utxo, other.final_script_sig, other.partial_sigs, other.sighash_type)
        )

    def deserialize(self, vds: BCDataStream):
        self._clear()  # Start fresh
        while vds.can_read_more():
            # Read key
            key = vds.read_bytes(strict=True)

            # Separator encountered, end of this input
            if len(key) == 0:
                return

            typ = key[0]

            if typ == PSBT_IN_UTXO:
                if self.utxo:
                    raise PSBTSerializationError("Duplicate Key, input utxo already provided")
                if len(key) != 1:
                    raise PSBTSerializationError("utxo key is more than one byte type")
                data = vds.read_bytes(strict=True)
                vds2 = BCDataStream(data)
                self.utxo = CTxOut()
                self.utxo.deserialize(vds2)
                if vds2.can_read_more():
                    raise PSBTSerializationError("utxo serialization has extra or unexpected bytes at the end")

            elif typ == PSBT_IN_PARTIAL_SIG:
                pubkey = _parse_pubkey(key)
                key_id = bitcoin.hash_160(pubkey)
                if key_id in self.partial_sigs:
                    raise PSBTSerializationError("Duplicate Key, input partial signature for pubkey already provided")

                sig = vds.read_bytes(strict=True)
                self.partial_sigs[key_id] = (pubkey, sig)

            elif typ == PSBT_IN_SIGHASH:
                if self.sighash_type != 0:
                    raise PSBTSerializationError("Duplicate Key, input sighash type already provided")
                if len(key) != 1:
                    raise PSBTSerializationError("Sighash type key is more than one byte type")
                data = vds.read_bytes(strict=True)
                vds2 = BCDataStream(data)
                self.sighash_type = vds2.read_uint32()
                if vds2.can_read_more():
                    raise PSBTSerializationError("sighash type serialization has extra or unexpected bytes at the end")

            elif typ == PSBT_IN_REDEEMSCRIPT:
                if self.redeem_script:
                    raise PSBTSerializationError("Duplicate Key, input redeemScript already provided")
                if len(key) != 1:
                    raise PSBTSerializationError("Input redeemScript key is more than one byte type")
                self.redeem_script = vds.read_bytes(strict=True)

            elif typ == PSBT_IN_BIP32_DERIVATION:
                _deserialize_hd_keypath(vds, key, self.hd_keypaths)

            elif typ == PSBT_IN_SCRIPTSIG:
                if self.final_script_sig:
                    raise PSBTSerializationError("Duplicate Key, input final scriptSig already provided")
                if len(key) != 1:
                    raise PSBTSerializationError("Final scriptSig key is more than one byte type")
                self.final_script_sig = vds.read_bytes(strict=True)

            # Unknown stuff
            else:
                _deserialize_unknown(vds, key, self.unknown)

    def serialize(self, vds: BCDataStream):
        # Write utxo
        if self.utxo is not None:
            vds.write_string(bytes((PSBT_IN_UTXO,)))
            # Serialize utxo to a vector then serialize that vector
            vds2 = BCDataStream()
            self.utxo.serialize(vds2)
            vds.write_string(vds2.input)

        if not self.final_script_sig:
            # Write any partial signatures
            for _, (pubkey, sig) in self.partial_sigs.items():
                vds.write_string(bytes((PSBT_IN_PARTIAL_SIG,)) + pubkey)
                vds.write_string(sig)

            # Write ths sighash type
            if self.sighash_type != 0:
                vds.write_string(bytes((PSBT_IN_SIGHASH,)))
                # Serialize sighash_type to a vector then serialize that vector
                vds2 = BCDataStream()
                vds2.write_uint32(self.sighash_type)
                vds.write_string(vds2.input)

            # Write the redeem script
            if self.redeem_script:
                vds.write_string(bytes((PSBT_IN_REDEEMSCRIPT,)))
                vds.write_string(self.redeem_script)

            # Write any hd keypaths
            _serialize_hd_keypaths(vds, self.hd_keypaths, PSBT_IN_BIP32_DERIVATION)
        else:
            # Write script sig
            vds.write_string(bytes((PSBT_IN_SCRIPTSIG,)))
            vds.write_string(self.final_script_sig)

        # Write unknown things
        _serialize_unknown(vds, self.unknown)

        vds.write_string(PSBT_SEPARATOR)


class PSBTOutput(_PSBTInputOutputBase):
    def __repr__(self):
        return f"<PSBTOutput {self._base_rep_str()}>"

    def __eq__(self, other):
        return isinstance(other, PSBTOutput) and super().__eq__(other)

    def deserialize(self, vds: BCDataStream):
        self._clear()  # Start fresh
        while vds.can_read_more():
            # Read key
            key = vds.read_bytes(strict=True)

            # Separator encountered, end of this output
            if len(key) == 0:
                return

            typ = key[0]

            if typ == PSBT_OUT_REDEEMSCRIPT:
                if self.redeem_script:
                    raise PSBTSerializationError("Duplicate Key, output redeemScript already provided")
                if len(key) != 1:
                    raise PSBTSerializationError("Output redeemScript key is more than one byte type")
                self.redeem_script = vds.read_bytes(strict=True)

            elif typ == PSBT_OUT_BIP32_DERIVATION:
                _deserialize_hd_keypath(vds, key, self.hd_keypaths)

            # Unknown stuff
            else:
                _deserialize_unknown(vds, key, self.unknown)

    def serialize(self, vds: BCDataStream):
        # Write the redeem script
        if self.redeem_script:
            vds.write_string(bytes([PSBT_OUT_REDEEMSCRIPT]))
            vds.write_string(self.redeem_script)

        # Write any hd keypaths
        _serialize_hd_keypaths(vds, self.hd_keypaths, PSBT_OUT_BIP32_DERIVATION)

        # Write unknown things
        _serialize_unknown(vds, self.unknown)

        vds.write_string(PSBT_SEPARATOR)


class PSBT:
    """Encapsulates a partially signed Bitcoin transaction."""
    tx: Optional[CMutableTransaction]
    inputs: List[PSBTInput]
    outputs: List[PSBTOutput]
    unknown: Dict[bytes, bytes]

    def __init__(self):
        self._clear()

    def _clear(self):
        self.tx = None
        self.inputs = []
        self.outputs = []
        self.unknown = {}

    def __repr__(self):
        unk = [(key.hex(), val.hex()) for key, val in self.unknown.items()]
        return f"<PSBT tx={self.tx!r} inputs={self.inputs!r} outputs={self.outputs!r} unknown={unk!r}>"

    def __eq__(self, other):
        return isinstance(other, PSBT) and (
            (self.tx, self.inputs, self.outputs, self.unknown) == (other.tx, other.inputs, other.outputs, other.unknown)
        )

    def deserialize(self, src: Union[bytes, bytearray, str, BCDataStream], *, is_hex=False):
        """Deserialize a partially signed bitcoin transaction. Takes a data stream, byte-like object or a
        base64-encoded string."""
        assert isinstance(src, (bytes, bytearray, str, BCDataStream))
        if isinstance(src, str):
            try:
                if is_hex:
                    decoded = bytes.fromhex(src)
                else:
                    decoded = binascii.a2b_base64(src)
            except binascii.Error as e:
                raise PSBTSerializationError("PSBT expects string argument to be base64-encoded") from e
            except ValueError as e:
                raise PSBTSerializationError("PSBT with is_hex=True expects string argument to be hex-encoded") from e
            vds = BCDataStream(decoded)
        elif isinstance(src, (bytes, bytearray)):
            vds = BCDataStream(src)
        else:
            vds: BCDataStream = src

        if vds.read_bytes(5, strict=False) != PSBT_MAGIC_BYTES:
            raise PSBTMagicBytesError("Invalid magic bytes")

        self._clear()

        while vds.can_read_more():
            # Read key
            key = vds.read_bytes(strict=True)

            # The key is empty if that was actually a separator byte. This is a special case for key lengths 0 as those
            # are not allowed (except for separator).
            if len(key) == 0:
                break

            # Do stuff based on type
            typ = key[0]
            if typ == PSBT_GLOBAL_UNSIGNED_TX:
                if len(key) != 1:
                    raise PSBTSerializationError("Global unsigned tx key is more than one byte")
                elif self.tx is not None:
                    raise PSBTSerializationError("Duplicate Key, unsigned tx already provided")
                txdata = vds.read_bytes(strict=True)
                vds2 = BCDataStream(txdata)
                self.tx = CMutableTransaction()
                self.tx.deserialize(vds2)
                if vds2.can_read_more():
                    raise PSBTSerializationError("transaction serialization has extra or unexpected bytes at the end")
                # Make sure that all scriptSigs are empty.
                for i, inp in enumerate(self.tx.vin):
                    assert isinstance(inp.script_sig, bytes), f"Input {i} must be bytes"
                    if len(inp.script_sig) != 0:
                        raise PSBTSerializationError(f"Unsigned tx has a non-empty empty scriptSig at input {i}")
            else:
                # Unknown stuff
                _deserialize_unknown(vds, key, self.unknown)

        # Make sure that we got an unsigned tx
        if not self.tx:
            raise PSBTSerializationError("No unsigned transcation was provided")

        # Read input data
        for i in range(len(self.tx.vin)):
            if not vds.can_read_more():
                raise PSBTSerializationError("Inputs provided does not match the number of inputs in transaction.")
            psbti = PSBTInput()
            psbti.deserialize(vds)
            self.inputs.append(psbti)

        # Read output data
        for i in range(len(self.tx.vout)):
            if not vds.can_read_more():
                raise PSBTSerializationError("Outputs provided does not match the number of inputs in transaction.")
            output = PSBTOutput()
            output.deserialize(vds)
            self.outputs.append(output)

    def serialize(self, vds: Optional[BCDataStream] = None, *, return_hex=False) -> Optional[str]:
        return_string = vds is None
        if not return_string and return_hex:
            warnings.warn("PSBT.serialize() called with return_hex=True and non-None vds; unsupported usage",
                          RuntimeWarning)
        vds = vds or BCDataStream()

        # magic bytes
        vds.write(PSBT_MAGIC_BYTES)

        # Enforce invariants related to the txn
        if not self.tx:
            raise PSBTSerializationError("No unsigned transaction was provided for serialization")
        elif any(inp.script_sig for inp in self.tx.vin):
            raise PSBTSerializationError("Unsigned transaction provided for serialization has non-empty scriptSig(s)")

        # unsigned tx flag
        vds.write_string(bytes((PSBT_GLOBAL_UNSIGNED_TX,)))

        # Write the serialized transaction to a stream
        vds2 = BCDataStream()
        self.tx.serialize(vds2)
        vds.write_string(vds2.input)

        # Write unknown things
        _serialize_unknown(vds, self.unknown)

        # Separator
        vds.write_string(PSBT_SEPARATOR)

        # Write inputs
        if len(self.inputs) != len(self.tx.vin):
            raise PSBTSerializationError("The number PSBT inputs must equal the unsigned tx's number of inputs")
        for inp in self.inputs:
            inp.serialize(vds)

        # Write outputs
        if len(self.outputs) != len(self.tx.vout):
            raise PSBTSerializationError("The number PSBT outputs must equal the unsigned tx's number of outputs")
        for outp in self.outputs:
            outp.serialize(vds)

        if return_string:
            if return_hex:
                return vds.input.hex()
            return binascii.b2a_base64(vds.input, newline=False).decode('ascii')

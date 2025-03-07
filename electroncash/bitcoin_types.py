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

"""Low-level primitives, as the C++ node software sees them. These
classes are more or less translated from the BCHN project's C++ file
primitives.h"""

from typing import List, Optional, Union

from . import bitcoin, token
from .serialize import BCDataStream


class uint256:
    data: bytes

    def __init__(self, data: Optional[Union[bytes, str]] = None):
        if data is None:
            self.data = b'\x00' * 32
        elif isinstance(data, (bytes, bytearray)):
            self.data = bytes(data)
        elif isinstance(data, str):
            self.data = bytes.fromhex(data)[::-1]
        else:
            raise TypeError("Bad argument type to uint256: " + str(type(data)))
        assert len(self.data) == 32

    def __str__(self):
        return self.data[::-1].hex()

    def __repr__(self):
        return f"<{self.__class__.__name__} {str(self)}>"

    def __bytes__(self):
        return self.data

    def __eq__(self, other):
        return isinstance(other, uint256) and self.data == other.data

    def serialize(self, vds: BCDataStream):
        assert len(self.data) == 32
        vds.write(self.data)

    def deserialize(self, vds: BCDataStream):
        self.data = vds.read_bytes(length=32, strict=True)
        assert len(self.data) == 32


class TxId(uint256):
    pass


class COutPoint:
    txid: TxId
    n: int

    def __init__(self, txid: Optional[Union[TxId, str, bytes]] = None, n=0):
        if txid is None:
            txid = TxId()
        elif isinstance(txid, (str, bytes)):
            # Caller specified a hex-encoded string, or a series of raw bytes
            txid = TxId(txid)
        assert isinstance(txid, TxId)
        self.txid = txid
        assert n >= 0
        self.n = n

    def __str__(self):
        return f"{self.txid}:{self.n}"

    def __repr__(self):
        return f"<COutPoint {self}>"

    def __eq__(self, other):
        return isinstance(other, COutPoint) and (self.txid, self.n) == (other.txid, other.n)

    def serialize(self, vds: BCDataStream):
        self.txid.serialize(vds)
        assert self.n >= 0
        vds.write_uint32(self.n)

    def deserialize(self, vds: BCDataStream):
        self.txid.deserialize(vds)
        self.n = vds.read_uint32()


class CTxIn:
    prevout: COutPoint
    script_sig: bytes
    sequence: int

    SEQUENCE_FINAL = 0xffffffff

    def __init__(self, prevout: Optional[COutPoint] = None, script_sig=b'', sequence=SEQUENCE_FINAL):
        self.prevout = prevout or COutPoint()
        self.script_sig = bytes(script_sig)
        self.sequence = sequence
        assert self.sequence >= 0

    def __repr__(self):
        return f"<CTxIn prevout={self.prevout} script_sig={self.script_sig.hex()} sequence=0x{self.sequence:x}>"

    def __eq__(self, other):
        return isinstance(other, CTxIn) and (
            (self.prevout, self.script_sig, self.sequence) == (other.prevout, other.script_sig, other.sequence))

    def serialize(self, vds: BCDataStream):
        self.prevout.serialize(vds)
        vds.write_string(self.script_sig)
        assert self.sequence >= 0
        vds.write_uint32(self.sequence)

    def deserialize(self, vds: BCDataStream):
        self.prevout.deserialize(vds)
        self.script_sig = vds.read_bytes(strict=True)
        self.sequence = vds.read_uint32()


class CTxOut:
    value: int
    script_pub_key: bytes
    token_data: Optional[token.OutputData]

    def __init__(self, value=0, script_pub_key=b'', token_data: Optional[token.OutputData] = None):
        self.value = value
        self.script_pub_key = bytes(script_pub_key)
        self.token_data = token_data

    def __repr__(self):
        return f"<CTxOut value={self.value} script_pub_key={self.script_pub_key.hex()} token_data={self.token_data!r}>"

    def __eq__(self, other):
        return isinstance(other, CTxOut) and (
            (self.value, self.script_pub_key, self.token_data) == (other.value, other.script_pub_key, other.token_data)
        )

    def serialize(self, vds: BCDataStream):
        vds.write_int64(self.value)
        wspk = token.wrap_spk(self.token_data, self.script_pub_key)
        vds.write_string(wspk)

    def deserialize(self, vds: BCDataStream):
        self.value = vds.read_int64()
        self.token_data, self.script_pub_key = token.unwrap_spk(vds.read_bytes(strict=True))


class CMutableTransaction:
    vin: List[CTxIn]
    vout: List[CTxOut]
    version: int = 2
    locktime: int = 0

    def __init__(self, vin: Optional[List[CTxIn]] = None, vout: Optional[List[CTxOut]] = None, version=2, locktime=0):
        self.vin = vin or []
        self.vout = vout or []
        self.version = version
        self.locktime = locktime
        assert 0 <= self.locktime < 2**32

    def __repr__(self):
        return f"<CMutableTransaction txid={self.txid} version={self.version} locktime={self.locktime}" \
               f" num_ins={len(self.vin)} num_outs={len(self.vout)} vin={self.vin!r}" \
               f" vout={self.vout!r}>"

    def __str__(self):
        return bytes(self).hex()

    def __bytes__(self):
        vds = BCDataStream()
        self.serialize(vds)
        return bytes(vds.input)

    def __eq__(self, other):
        return isinstance(other, CMutableTransaction) and (
            (self.vin, self.vout, self.version, self.locktime) == (other.vin, other.vout, other.version, other.locktime)
        )

    @property
    def txid(self) -> TxId:
        return TxId(bitcoin.Hash(bytes(self)))

    @property
    def id(self) -> TxId: return self.txid

    def serialize(self, vds: BCDataStream):
        vds.write_int32(self.version)
        vds.write_compact_size(len(self.vin))
        for inp in self.vin:
            inp.serialize(vds)
        vds.write_compact_size(len(self.vout))
        for outp in self.vout:
            outp.serialize(vds)
        vds.write_uint32(self.locktime)

    def deserialize(self, vds: BCDataStream):
        self.version = vds.read_int32()
        num_ins = vds.read_compact_size(strict=True)
        self.vin = []
        for _ in range(num_ins):
            inp = CTxIn()
            inp.deserialize(vds)
            self.vin.append(inp)
        num_outs = vds.read_compact_size(strict=True)
        self.vout = []
        for _ in range(num_outs):
            outp = CTxOut()
            outp.deserialize(vds)
            self.vout.append(outp)
        self.locktime = vds.read_uint32()

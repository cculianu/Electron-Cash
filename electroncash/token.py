#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- mode: python3 -*-
# This file (c) 2022 Calin Culianu <calin.culianu@gmail.com>
# Part of the Electron Cash SPV Wallet
# License: MIT
"""Encapsulation of Cash Token data in a transaction output"""

from enum import IntEnum
import struct
from typing import Optional, Tuple, Union

from .bitcoin import OpCodes
from .serialize import BCDataStream, SerializationError


class Structure(IntEnum):
    HasAmount = 0x10
    HasNFT = 0x20
    HasCommitmentLength = 0x40


class Capability(IntEnum):
    NoCapability = 0x00
    Mutable = 0x01
    Minting = 0x02


class OutputData:
    __slots__ = ("id", "bitfield", "amount", "commitment")

    def __init__(self, id: Union[bytes, str] = b'\x00' * 32, amount: int = 1, commitment: Union[bytes, str] = b'',
                 bitfield: Union[int, str, bytes] = Structure.HasAmount):
        if isinstance(id, str):
            # Convert from hex and reverse
            id = bytes.fromhex(id)[::-1]
        if isinstance(commitment, str):
            # Convert from hex, don't reverse
            commitment = bytes.fromhex(commitment)
        if isinstance(bitfield, str):
            # Convert from hex (must be 1 byte hex)
            assert len(bitfield) == 2
            bitfield = bytes.fromhex(bitfield)[0]
        elif isinstance(bitfield, bytes):
            # Convert from bytes (must be length 1)
            assert len(bitfield) == 1
            bitfield = bitfield[0]
        assert len(id) == 32 and (isinstance(id, bytes) and isinstance(commitment, bytes) and isinstance(bitfield, int)
                                  and isinstance(amount, int))
        self.id = id
        self.amount = amount
        self.commitment = commitment
        self.bitfield = bitfield

    def __eq__(self, other) -> bool:
        if not isinstance(other, OutputData):
            return False
        return (self.id, self.bitfield, self.amount, self.commitment) == (other.id, other.bitfield, other.amount,
                                                                          other.commitment)

    def __repr__(self) -> str:
        return f"<token.OutputData(id={self.id_hex}, bitfield={self.bitfield:02x}, amount={self.amount}, " \
               f"commitment={self.commitment[:40].hex()})>"

    @property
    def id_hex(self) -> str:
        return self.id[::-1].hex()

    @id_hex.setter
    def id_hex(self, hex: str):
        b = bytes.fromhex(hex)
        assert len(b) == 32
        self.id = b[::-1]

    def deserialize(self, *, buffer: Optional[bytes] = None, ds: Optional[BCDataStream] = None):
        assert bool(buffer is not None) + bool(ds is not None) == 1  # Exactly one of these must be valid
        if ds is None:
            ds = BCDataStream(buffer)
        self.id = ds.read_bytes(32, strict=True)
        self.bitfield = struct.unpack("<B", ds.read_bytes(1, strict=True))[0]
        if self.has_commitment_length():
            self.commitment = ds.read_bytes(strict=True)
        else:
            self.commitment = b''
        if self.has_amount():
            self.amount = ds.read_compact_size(strict=True)
        else:
            self.amount = 0
        if (not self.is_valid_bitfield() or (self.has_amount() and not self.amount)
                or self.amount < 0 or self.amount > 2**63-1
                or (self.has_commitment_length() and not self.commitment)
                or (not self.amount and not self.has_nft())):
            # Bad bitfield or 0 serialized amount or bad amount or empty serialized commitment is
            # a deserialization error
            raise SerializationError('Unable to parse token data or token data is invalid')

    def serialize(self) -> bytes:
        ds = BCDataStream()
        ds.write(self.id)
        ds.write(struct.pack("B", self.bitfield))
        if self.has_commitment_length():
            ds.write_compact_size(len(self.commitment))
            ds.write(self.commitment)
        if self.has_amount():
            ds.write_compact_size(self.amount)
        return bytes(ds.input)

    def get_capability(self) -> int:
        return self.bitfield & 0x0f

    def has_commitment_length(self) -> bool:
        return bool(self.bitfield & Structure.HasCommitmentLength)

    def has_amount(self) -> bool:
        return bool(self.bitfield & Structure.HasAmount)

    def has_nft(self) -> bool:
        return bool(self.bitfield & Structure.HasNFT)

    def is_minting_nft(self) -> bool:
        return self.has_nft() and self.get_capability() == Capability.Minting

    def is_mutable_nft(self) -> bool:
        return self.has_nft() and self.get_capability() == Capability.Mutable

    def is_immutable_nft(self) -> bool:
        return self.has_nft() and self.get_capability() == Capability.NoCapability

    def is_valid_bitfield(self) -> bool:
        s = self.bitfield & 0xf0
        if s >= 0x80 or s == 0x00:
            return False
        if self.bitfield & 0x0f > 2:
            return False
        if not self.has_nft() and not self.has_amount():
            return False
        if not self.has_nft() and (self.bitfield & 0x0f) != 0:
            return False
        if not self.has_nft() and self.has_commitment_length():
            return False
        return True


PREFIX_BYTE = bytes([OpCodes.SPECIAL_TOKEN_PREFIX])


def wrap_spk(token_data: Optional[OutputData], script_pub_key: bytes) -> bytes:
    if not token_data:
        return script_pub_key
    buf = bytearray()
    assert len(PREFIX_BYTE) == 1
    buf += PREFIX_BYTE
    buf += token_data.serialize()
    buf += script_pub_key
    return bytes(buf)


def unwrap_spk(wrapped_spk: bytes) -> Tuple[Optional[OutputData], bytes]:
    assert len(PREFIX_BYTE) == 1
    if not wrapped_spk or wrapped_spk[0] != PREFIX_BYTE[0]:
        return None, wrapped_spk
    token_data = OutputData()
    ds = BCDataStream(wrapped_spk)
    pfx = ds.read_bytes(1, strict=True)  # consume prefix byte
    assert pfx == PREFIX_BYTE
    try:
        token_data.deserialize(ds=ds)  # unserialize token_data from buffer after prefix_byte
    except SerializationError:
        # Unable to deserialize or parse token data. This is ok. Just return all the bytes as the full scriptPubKey
        return None, wrapped_spk
    # leftover bytes go to real spk
    spk = wrapped_spk[ds.read_cursor:]
    return token_data, spk  # Parsed ok

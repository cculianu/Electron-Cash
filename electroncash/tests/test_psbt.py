import unittest

from ..bitcoin_types import COutPoint
from ..psbt import PSBT


class TestPSBT(unittest.TestCase):

    def test_basic_ser_deser(self):
        raw_psbt = ("70736274ff0100a0020000000258e87a21b56daf0c23be8e7070456c336f7cbaa5c875"
                    "7924f545887bb2abdd750000000000ffffffff6b04ec37326fbac8e468a73bf952c887"
                    "7f84f96c3f9deadeab246455e34fe0cd0100000000ffffffff0270aaf0080000000019"
                    "76a914d85c2b71d0060b09c9886aeb815e50991dda124d88ac00e1f505000000001976"
                    "a91400aea9a2e5f0f876a588df5546e8742d1d87008f88ac000000000001002080f0fa"
                    "020000000017a9140fb9463421696b82c833af241c78c17ddbde493487010447522102"
                    "9583bf39ae0a609747ad199addd634fa6108559d6c5cd39b4c2183f1ab96e07f2102da"
                    "b61ff49a14db6a7d02b0cd1fbb78fc4b18312b5b4e54dae4dba2fbfef536d752ae2206"
                    "029583bf39ae0a609747ad199addd634fa6108559d6c5cd39b4c2183f1ab96e07f10d9"
                    "0c6a4f000000800000008000000080220602dab61ff49a14db6a7d02b0cd1fbb78fc4b"
                    "18312b5b4e54dae4dba2fbfef536d710d90c6a4f000000800000008001000080000100"
                    "2000c2eb0b0000000017a914f6539307e3a48d1e0136d061f5d1fe19e1a24089870104"
                    "47522103089dc10c7ac6db54f91329af617333db388cead0c231f723379d1b99030b02"
                    "dc21023add904f3d6dcf59ddb906b0dee23529b7ffb9ed50e5e86151926860221f0e73"
                    "52ae2206023add904f3d6dcf59ddb906b0dee23529b7ffb9ed50e5e86151926860221f"
                    "0e7310d90c6a4f000000800000008003000080220603089dc10c7ac6db54f91329af61"
                    "7333db388cead0c231f723379d1b99030b02dc10d90c6a4f0000008000000080020000"
                    "8000220203a9a4c37f5996d3aa25dbac6b570af0650394492942460b354753ed9eeca5"
                    "877110d90c6a4f000000800000008004000080002202027f6399757d2eff55a136ad02"
                    "c684b1838b6556e5f1b6b34282a94b6b5005109610d90c6a4f00000080000000800500"
                    "008000")
        # Test ser/unser round-trip preserves data
        ptx = PSBT()
        ptx.deserialize(raw_psbt, is_hex=True)
        self.assertEqual(ptx.serialize(return_hex=True), raw_psbt)

        ptx2 = PSBT()
        ptx2.deserialize(ptx.serialize())
        self.assertEqual(ptx, ptx2)
        self.assertEqual(ptx2.serialize(return_hex=True), raw_psbt)
        self.assertEqual(ptx.serialize(), ptx2.serialize())

        # Implicitly test equality operator for CMutableTransaction and its nested types
        self.assertIsNotNone(ptx.tx)
        self.assertIsNotNone(ptx2.tx)
        self.assertFalse(ptx.tx is ptx2.tx)
        self.assertEqual(ptx.tx, ptx2.tx)

        # Lastly, test that the decoded psbt tx has the data attributes we expect
        # 1. `tx` attribute
        self.assertEqual(str(ptx.tx.txid), "6d22ead0a603fdf0aa643a0109d4051de19ec94cfe1bd1ea7c241990d8a02ad5")
        self.assertEqual(ptx.tx.txid.data,
                         bytes.fromhex("6d22ead0a603fdf0aa643a0109d4051de19ec94cfe1bd1ea7c241990d8a02ad5")[::-1])
        self.assertEqual(bytes(ptx.tx.txid),
                         bytes.fromhex("6d22ead0a603fdf0aa643a0109d4051de19ec94cfe1bd1ea7c241990d8a02ad5")[::-1])
        self.assertEqual(len(bytes(ptx.tx)), 160)
        self.assertEqual(ptx.tx.version, 2)
        self.assertEqual(ptx.tx.locktime, 0)
        self.assertEqual(len(ptx.tx.vin), 2)
        self.assertEqual(len(ptx.tx.vout), 2)
        self.assertEqual(ptx.tx.vin[0].prevout,
                         COutPoint("75ddabb27b8845f5247975c8a5ba7c6f336c4570708ebe230caf6db5217ae858", 0))
        self.assertEqual(str(ptx.tx.vin[0].prevout),
                         "75ddabb27b8845f5247975c8a5ba7c6f336c4570708ebe230caf6db5217ae858:0")
        self.assertEqual(ptx.tx.vin[1].prevout,
                         COutPoint("cde04fe3556424abdeea9d3f6cf9847f87c852f93ba768e4c8ba6f3237ec046b", 1))
        self.assertEqual(str(ptx.tx.vin[1].prevout),
                         "cde04fe3556424abdeea9d3f6cf9847f87c852f93ba768e4c8ba6f3237ec046b:1")
        self.assertEqual(ptx.tx.vin[0].script_sig, b'')
        self.assertEqual(ptx.tx.vin[1].script_sig, b'')
        self.assertEqual(ptx.tx.vout[0].script_pub_key.hex(), "76a914d85c2b71d0060b09c9886aeb815e50991dda124d88ac")
        self.assertEqual(ptx.tx.vout[0].value, 1_49990000)
        self.assertEqual(ptx.tx.vout[1].script_pub_key.hex(), "76a91400aea9a2e5f0f876a588df5546e8742d1d87008f88ac")
        self.assertEqual(ptx.tx.vout[1].value, 1_00000000)
        # 2. `inputs` attribute
        self.assertEqual(len(ptx.inputs), 2)
        self.assertFalse(any(inp.unknown for inp in ptx.inputs))
        self.assertEqual(ptx.inputs[0].utxo.script_pub_key.hex(), "a9140fb9463421696b82c833af241c78c17ddbde493487")
        self.assertEqual(ptx.inputs[1].utxo.script_pub_key.hex(), "a914f6539307e3a48d1e0136d061f5d1fe19e1a2408987")
        self.assertEqual(ptx.inputs[0].utxo.value, 50000000)
        self.assertEqual(ptx.inputs[1].utxo.value, 2_00000000)
        self.assertFalse(any(inp.utxo.token_data for inp in ptx.inputs))
        self.assertEqual(ptx.inputs[0].final_script_sig, b'')
        self.assertEqual(ptx.inputs[1].final_script_sig, b'')
        self.assertEqual(ptx.inputs[0].redeem_script.hex(), "5221029583bf39ae0a609747ad199addd634fa6108559d6c5cd39b4c21"
                                                            "83f1ab96e07f2102dab61ff49a14db6a7d02b0cd1fbb78fc4b18312b5b"
                                                            "4e54dae4dba2fbfef536d752ae")
        self.assertEqual(ptx.inputs[1].redeem_script.hex(), "522103089dc10c7ac6db54f91329af617333db388cead0c231f723379d"
                                                            "1b99030b02dc21023add904f3d6dcf59ddb906b0dee23529b7ffb9ed50"
                                                            "e5e86151926860221f0e7352ae")
        pubkey0 = bytes.fromhex("029583bf39ae0a609747ad199addd634fa6108559d6c5cd39b4c2183f1ab96e07f")
        pubkey1 = bytes.fromhex("02dab61ff49a14db6a7d02b0cd1fbb78fc4b18312b5b4e54dae4dba2fbfef536d7")
        fingerprint = bytes.fromhex("d90c6a4f")
        self.assertEqual(ptx.inputs[0].hd_keypaths[pubkey0].fingerprint, fingerprint)
        self.assertEqual(ptx.inputs[0].hd_keypaths[pubkey1].fingerprint, fingerprint)
        self.assertEqual(ptx.inputs[0].hd_keypaths[pubkey0].path_str, "m/0'/0'/0'")
        self.assertEqual(ptx.inputs[0].hd_keypaths[pubkey1].path_str, "m/0'/0'/1'")
        pubkey0 = bytes.fromhex("023add904f3d6dcf59ddb906b0dee23529b7ffb9ed50e5e86151926860221f0e73")
        pubkey1 = bytes.fromhex("03089dc10c7ac6db54f91329af617333db388cead0c231f723379d1b99030b02dc")
        self.assertEqual(ptx.inputs[1].hd_keypaths[pubkey0].fingerprint, fingerprint)
        self.assertEqual(ptx.inputs[1].hd_keypaths[pubkey1].fingerprint, fingerprint)
        self.assertEqual(ptx.inputs[1].hd_keypaths[pubkey0].path_str, "m/0'/0'/3'")
        self.assertEqual(ptx.inputs[1].hd_keypaths[pubkey1].path_str, "m/0'/0'/2'")
        # 3. `outputs` attribute
        pubkey0 = bytes.fromhex("03a9a4c37f5996d3aa25dbac6b570af0650394492942460b354753ed9eeca58771")
        pubkey1 = bytes.fromhex("027f6399757d2eff55a136ad02c684b1838b6556e5f1b6b34282a94b6b50051096")
        self.assertEqual(ptx.outputs[0].hd_keypaths[pubkey0].fingerprint, fingerprint)
        self.assertEqual(ptx.outputs[0].hd_keypaths[pubkey0].path_str, "m/0'/0'/4'")
        self.assertEqual(ptx.outputs[1].hd_keypaths[pubkey1].fingerprint, fingerprint)
        self.assertEqual(ptx.outputs[1].hd_keypaths[pubkey1].path_str, "m/0'/0'/5'")
        # 4. `unknown` attribute
        self.assertEqual(ptx.unknown, ptx2.unknown)
        self.assertEqual(ptx.unknown, dict())

        fee = sum(inp.utxo.value for inp in ptx.inputs) - sum(outp.value for outp in ptx.tx.vout)
        self.assertEqual(fee, 10000)

        # Test that calling deserialize on an existing object clears it correctly and re-inits it correctly
        other_psbt64 = ('cHNidP8BAFUCAAAAAQYzCdm3wW2eMlfpXZWPJWHiKL0eTboVXoLR8UWVDRtMAQAAAAD+////AUHg9QUAAAAAGXapFFsLO'
                        'OuZXnYrjT1B43DjKiMESP/RiKwAAAAAAAEAIgDh9QUAAAAAGXapFPNE2zFEjhpes6/Jz+a0qkpPF2AbiKwiBgNlj2uZsI'
                        'HxYysuuf3RdIuaNPv+1Arr5GELK+jvU2J3xBDbPmF0AAAAgAAAAIAAAACAAAA=')
        ptx2.deserialize(other_psbt64)
        self.assertNotEqual(ptx, ptx2)
        self.assertEqual(ptx2.serialize(), other_psbt64)
        # Re-init again from the same serialization as ptx, and ensure nothing changed
        ptx2.deserialize(ptx.serialize())
        self.assertEqual(ptx, ptx2)
        self.assertNotEqual(ptx2.serialize(), other_psbt64)

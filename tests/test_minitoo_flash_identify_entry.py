"""Execute the pinned entry adapter's small instruction subset offline.

The C callee is substituted with an ABI-conforming, caller-clobbering function.
This tests the adapter, not PI32 silicon or interrupt-stack behaviour.
"""
import struct
import unittest
from test_minitoo_flash_identify import captured_block, m


class EntryTests(unittest.TestCase):
    def simulate(self, caller_sp, caller_return, damage_guard=False):
        code = m.payload.make_block()
        registers = {f'r{i}': 0xA0000000+i for i in range(16)}
        registers.update(sp=caller_sp, rets=caller_return)
        preserved = {f'r{i}': registers[f'r{i}'] for i in range(4,16)}
        memory, writes, calls = {}, [], []
        pc = 0

        def store(address, value):
            memory[address] = value
            writes.append(address)

        for _ in range(40):
            op = code[pc:pc+2]
            if op in (b'\xc0\xff', b'\xc1\xff', b'\xee\xff'):
                name = {b'\xc0\xff':'r0', b'\xc1\xff':'r1', b'\xee\xff':'sp'}[op]
                registers[name] = struct.unpack_from('<I', code, pc+2)[0]
                pc += 6
            elif code[pc:pc+4] in (bytes.fromhex('64e0000e'), bytes.fromhex('64e00003'),
                                   bytes.fromhex('64e0800e'), bytes.fromhex('64e08003')):
                dst, src = {bytes.fromhex('64e0000e'):('r0','sp'),
                            bytes.fromhex('64e00003'):('r0','rets'),
                            bytes.fromhex('64e0800e'):('sp','r0'),
                            bytes.fromhex('64e08003'):('rets','r0')}[code[pc:pc+4]]
                registers[dst] = registers[src]
                pc += 4
            elif op in (bytes.fromhex('9060'), bytes.fromhex('9061'), bytes.fromhex('8160')):
                base, offset, src = {bytes.fromhex('9060'):('r1',0,'r0'),
                                     bytes.fromhex('9061'):('r1',4,'r0'),
                                     bytes.fromhex('8160'):('r0',0,'r1')}[op]
                store(registers[base]+offset, registers[src])
                pc += 2
            elif op in (bytes.fromhex('0160'), bytes.fromhex('1061'), bytes.fromhex('1060')):
                dst, base, offset = {bytes.fromhex('0160'):('r1','r0',0),
                                     bytes.fromhex('1061'):('r0','r1',4),
                                     bytes.fromhex('1060'):('r0','r1',0)}[op]
                registers[dst] = memory[registers[base]+offset]
                pc += 2
            elif op == bytes.fromhex('80ea'):
                target = m.payload.ADDRESS + pc + 4 + 2*struct.unpack_from('<h',code,pc+2)[0]
                self.assertEqual(target, 0x120076)
                self.assertEqual(registers['sp'], m.payload.STACK_TOP)
                self.assertEqual(registers['r0'], m.payload.ADDRESS+m.payload.RESULT_OFFSET)
                self.assertEqual(memory[0x1207F8], caller_sp)
                self.assertEqual(memory[0x1207FC], caller_return)
                self.assertEqual(memory[m.payload.STACK_BOTTOM], m.payload.STACK_GUARD)
                # C may use the private stack and clobber caller-saved registers
                # and RETS, but must return SP and callee-saved registers intact.
                store(registers['sp']-92, 0xDEADBEEF)
                for i in range(4):
                    registers[f'r{i}'] = 0xBA000000+i
                registers['rets'] = 0x120244
                if damage_guard:
                    store(m.payload.STACK_BOTTOM, 0)
                calls.append(target)
                pc += 4
            elif op == bytes.fromhex('8000'):
                self.assertEqual(pc, 0x52)
                break
            else:
                self.fail(f'Unreviewed adapter instruction at {pc:x}')
        else:
            self.fail('Adapter did not return')
        self.assertEqual(registers['sp'], caller_sp)
        self.assertEqual(registers['rets'], caller_return)
        self.assertEqual({k:registers[k] for k in preserved}, preserved)
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(0x120740 <= a < 0x120800
                            or m.payload.STACK_BOTTOM <= a < m.payload.STACK_TOP for a in writes))
        return memory

    def test_adapter_restores_context_after_c_clobbers(self):
        for sp in (0x180820,0x180FB0,0x181020,0x19FC00,0x19FFFC):
            for ret in (0x4ABC,0x87654320):
                self.assertEqual(self.simulate(sp,ret)[0x120794], m.payload.STACK_GUARD)

    def test_damaged_stack_guard_is_reported_and_rejected(self):
        memory = self.simulate(0x180FB0,0x4ABC,True)
        block = bytearray(captured_block())
        struct.pack_into('<I',block,0x794,memory[0x120794])
        with self.assertRaises(ValueError):
            m.payload.decode_result(bytes(block))


if __name__ == '__main__':
    unittest.main()

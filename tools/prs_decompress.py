# SEGA PRS Decompression (LZS variant)
# Based on public-domain code from qhimm.com forums (Micky, 2011)
import array

class DecompressPrs:
    def __init__(self, data):
        self.ibuf = array.array("B", data)
        self.obuf = array.array("B")
        self.iofs = 0
        self.bit = 0
        self.cmd = 0

    def getByte(self):
        val = self.ibuf[self.iofs]
        self.iofs += 1
        return val

    def getBit(self):
        if self.bit == 0:
            self.cmd = self.getByte()
            self.bit = 8
        bit = self.cmd & 1
        self.cmd >>= 1
        self.bit -= 1
        return bit

    def decompress(self):
        while self.iofs < len(self.ibuf):
            cmd = self.getBit()
            if cmd:
                self.obuf.append(self.ibuf[self.iofs])
                self.iofs += 1
            else:
                t = self.getBit()
                if t:
                    a = self.getByte()
                    b = self.getByte()
                    offset = ((b << 8) | a) >> 3
                    amount = a & 7
                    if self.iofs < len(self.ibuf):
                        if amount == 0:
                            amount = self.getByte() + 1
                        else:
                            amount += 2
                    start = len(self.obuf) - 0x2000 + offset
                else:
                    amount = 0
                    for j in range(2):
                        amount <<= 1
                        amount |= self.getBit()
                    offset = self.getByte()
                    amount += 2
                    start = len(self.obuf) - 0x100 + offset
                for j in range(amount):
                    if start < 0:
                        self.obuf.append(0)
                    elif start < len(self.obuf):
                        self.obuf.append(self.obuf[start])
                    else:
                        self.obuf.append(0)
                    start += 1
        return self.obuf.tobytes()

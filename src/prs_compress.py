"""PRS(SEGA LZ77) 압축기. src/export_images.py의 decompress()와 짝을 이룬다.

명령 비트는 LSB부터 쓰고, 새 명령 바이트는 그 묶음의 첫 비트를 쓸 때 자리를 잡는다.
  1            : 리터럴 1바이트
  0 0 b1 b0 d  : 짧은 복사, 길이 2~5, 거리 1~256 (d = 0x100 - 거리)
  0 1 a b [n]  : 긴 복사, 거리 1~0x1FFF. 길이 3~9는 a 하위 3비트(길이-2),
                 길이 10~256은 하위 3비트 0 + 다음 바이트(길이-1)
  0 1 00 00    : 끝 표시
"""

MAX_LONG_DIST = 0x1FFF
MAX_SHORT_DIST = 0x100
MAX_LEN = 0x100
CHAIN = 48


class _Writer:
    def __init__(self):
        self.out = bytearray()
        self.cmd = 0
        self.n = 0

    def bit(self, b):
        if self.n == 0:
            self.cmd = len(self.out)
            self.out.append(0)
        if b:
            self.out[self.cmd] |= 1 << self.n
        self.n = (self.n + 1) & 7

    def byte(self, v):
        self.out.append(v)


def compress(data):
    data = bytes(data)
    n = len(data)
    w = _Writer()
    head = {}
    prev = [-1] * n
    pos = 0

    def insert(i):
        if i + 2 < n:
            k = data[i:i + 3]
            prev[i] = head.get(k, -1)
            head[k] = i

    while pos < n:
        best_len, best_dist = 0, 0
        if pos + 2 < n:
            cand = head.get(data[pos:pos + 3], -1)
            limit = min(MAX_LEN, n - pos)
            tries = CHAIN
            while cand >= 0 and tries:
                d = pos - cand
                if d > MAX_LONG_DIST:
                    break
                if data[cand + best_len] == data[pos + best_len] if best_len < limit else False:
                    l = 3
                    while l < limit and data[cand + l] == data[pos + l]:
                        l += 1
                    if l > best_len:
                        best_len, best_dist = l, d
                        if l == limit:
                            break
                cand = prev[cand]
                tries -= 1
        # 길이 2짜리 짧은 복사(3바이트 해시로는 못 찾음)
        if best_len < 3 and pos + 1 < n:
            lo = max(0, pos - MAX_SHORT_DIST)
            j = data.rfind(data[pos:pos + 2], lo, pos + 1)
            if 0 <= j < pos:
                best_len, best_dist = 2, pos - j
                l = 2
                while l < 5 and pos + l < n and data[j + l] == data[pos + l]:
                    l += 1
                best_len = l
        if best_len >= 2 and best_len <= 5 and best_dist <= MAX_SHORT_DIST:
            w.bit(0); w.bit(0)
            c = best_len - 2
            w.bit(c >> 1); w.bit(c & 1)
            w.byte(MAX_SHORT_DIST - best_dist)
        elif best_len >= 3:
            off = (0x2000 - best_dist) << 3
            w.bit(0); w.bit(1)
            if best_len <= 9:
                v = off | (best_len - 2)
                w.byte(v & 0xFF); w.byte(v >> 8)
            else:
                w.byte(off & 0xFF); w.byte(off >> 8); w.byte(best_len - 1)
        else:
            w.bit(1)
            w.byte(data[pos])
            best_len = 1
        for i in range(pos, pos + best_len):
            insert(i)
        pos += best_len
    w.bit(0); w.bit(1); w.byte(0); w.byte(0)
    return bytes(w.out)


def compress_optimal(data, chain=64):
    """비트 비용 최소 경로(DP)로 고르는 PRS 압축. compress()보다 느리지만 5~10% 작다.
    비용(비트): 리터럴 9, 짧은 복사 12, 긴 복사(3~9) 18, 긴 복사(10~256) 26."""
    data = bytes(data)
    n = len(data)
    # 위치별 후보: (거리, 최대 길이) — 해시 체인으로 찾는다
    head = {}
    prev = [-1] * n
    cands = [None] * n
    for pos in range(n):
        found = []
        if pos + 2 < n:
            k = data[pos:pos + 3]
            cand = head.get(k, -1)
            limit = min(MAX_LEN, n - pos)
            tries = chain
            best = 2
            while cand >= 0 and tries:
                d = pos - cand
                if d > MAX_LONG_DIST:
                    break
                if data[cand + best] == data[pos + best] if best < limit else False:
                    l = 3
                    while l < limit and data[cand + l] == data[pos + l]:
                        l += 1
                    if l > best:
                        found.append((d, l))
                        best = l
                        if l == limit:
                            break
                cand = prev[cand]
                tries -= 1
            prev[pos] = head.get(k, -1)
            head[k] = pos
        if pos + 1 < n:
            lo = max(0, pos - MAX_SHORT_DIST)
            j = data.rfind(data[pos:pos + 2], lo, pos + 1)
            if 0 <= j < pos:
                l = 2
                while l < 5 and pos + l < n and data[j + l] == data[pos + l]:
                    l += 1
                found.append((pos - j, l))
        cands[pos] = found
    INF = 1 << 60
    cost = [INF] * (n + 1)
    choice = [None] * (n + 1)
    cost[n] = 0
    for pos in range(n - 1, -1, -1):
        bc, bch = cost[pos + 1] + 9, (1, 0)
        for d, L in cands[pos]:
            if d <= MAX_SHORT_DIST:
                for l in range(2, min(L, 5) + 1):
                    c = cost[pos + l] + 12
                    if c < bc:
                        bc, bch = c, (l, d)
            if L >= 3:
                for l in (9, L) if L > 9 else (L,):  # 9(싼 표기)와 최대 길이만 본다
                    c = cost[pos + l] + (18 if l <= 9 else 26)
                    if c < bc:
                        bc, bch = c, (l, d)
        cost[pos], choice[pos] = bc, bch
    w = _Writer()
    pos = 0
    while pos < n:
        l, d = choice[pos]
        if d == 0:
            w.bit(1); w.byte(data[pos])
        elif l <= 5 and d <= MAX_SHORT_DIST:
            w.bit(0); w.bit(0)
            c = l - 2
            w.bit(c >> 1); w.bit(c & 1)
            w.byte(MAX_SHORT_DIST - d)
        else:
            off = (0x2000 - d) << 3
            w.bit(0); w.bit(1)
            if l <= 9:
                v = off | (l - 2)
                w.byte(v & 0xFF); w.byte(v >> 8)
            else:
                w.byte(off & 0xFF); w.byte(off >> 8); w.byte(l - 1)
        pos += l
    w.bit(0); w.bit(1); w.byte(0); w.byte(0)
    return bytes(w.out)

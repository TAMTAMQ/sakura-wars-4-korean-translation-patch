"""LIPSYNC 자막 타이핑 시점을 한글 문장에 맞춘다.

LIP 항목은 [대사 NUL][입 모양 스트림 … 00][다음 대사] 순서다. 스트림은 1프레임당
4비트(바이트 하나에 두 프레임)이고 값 1~5는 입 모양, 6은 다문 입, 7은 「다음 글자 하나를
찍는다」는 표시다. 원본에서 7의 개수는 대사 글자 수(줄바꿈 // 제외)와 정확히 같다.

번역문은 글자 수와 어순이 달라 글자 순번대로 7을 받으면 엉뚱한 때에 글자가 찍힌다
(예: 「아아…오」의 「오」가 일본어 둘째 「…」의 무음 구간에서 찍힘). 그래서
  1) 원문과 번역문의 문장부호(문장 끝·말줄임·쉼표)를 순서대로 짝지어 기준점으로 삼고
     (번역문의 「…」는 원문 「……」의 첫 글자 시점에 찍는다),
  2) 기준점 사이의 한글 글자는 그 구간에서 실제로 소리가 나는 프레임(긴 다문 입 제외)에
     고르게 놓는다.
스트림 길이와 위치는 바꾸지 않는다.
"""
END = set('。．！？∈〓!?')
DOTS = set('…‥')
COMMA = set('、，,')
SILENT_RUN = 4          # 이 길이 이상 이어지는 다문 입(6)은 무음 구간으로 본다


def nibbles(data):
    return [v for b in data for v in (b >> 4, b & 15)]


def pack(nibs):
    return bytes((nibs[i] << 4) | nibs[i + 1] for i in range(0, len(nibs), 2))


def kind(c):
    if c in END:
        return 'end'
    if c in DOTS:
        return 'dots'
    if c in COMMA:
        return 'comma'
    return None


def groups(chars):
    """연속한 같은 종류 문장부호를 한 덩어리로: [(종류, 시작, 끝)]"""
    out = []
    i = 0
    while i < len(chars):
        k = kind(chars[i])
        if k:
            j = i
            while j < len(chars) and kind(chars[j]) == k:
                j += 1
            out.append((k, i, j))
            i = j
        else:
            i += 1
    return out


def score(jk, kk, jpos, kpos):
    """원문 문장부호 덩어리와 번역문 경계(문장부호 덩어리 또는 띄어쓰기)의 짝 점수."""
    if kk == 'space':
        base = {'end': 4, 'dots': 4, 'comma': 2}[jk]
    elif jk == kk:
        base = {'end': 6, 'dots': 5, 'comma': 3}[jk]
    else:
        base = 3                     # 종류만 다른 문장부호(？↔，, ……↔∈ 등)
    return base - 8 * abs(jpos - kpos)


def match(jg, kg, nj, nk):
    """원문 문장부호 덩어리와 번역문 경계를 순서를 지키며 짝짓는다(가중 LCS, 상대 위치가 멀면 감점)."""
    n, m = len(jg), len(kg)
    sc = [[score(jg[a][0], kg[b][0], jg[a][2] / nj, kg[b][2] / nk) for b in range(m)] for a in range(n)]
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for a in range(n - 1, -1, -1):
        for b in range(m - 1, -1, -1):
            v = max(best[a + 1][b], best[a][b + 1])
            if sc[a][b] > 0:
                v = max(v, best[a + 1][b + 1] + sc[a][b])
            best[a][b] = v
    pairs = []
    a = b = 0
    while a < n and b < m:
        if sc[a][b] > 0 and abs(best[a][b] - (best[a + 1][b + 1] + sc[a][b])) < 1e-9:
            pairs.append((jg[a], kg[b]))
            a += 1
            b += 1
        elif best[a + 1][b] >= best[a][b + 1]:
            a += 1
        else:
            b += 1
    return pairs


def retime(stream, jp_chars, ko_chars, ko_spaces=()):
    """스트림(바이트, 끝 00 제외)을 한글 글자 배치에 맞게 다시 쓴다. 맞출 수 없으면 None.
    ko_spaces: 뒤에 띄어쓰기가 붙은 ko_chars 순번."""
    nib = nibbles(stream)
    marks = [i for i, v in enumerate(nib) if v == 7]
    if len(marks) != len(jp_chars) or not ko_chars or len(ko_chars) > len(nib):
        return None
    L = len(nib)
    # 소리 나는 프레임: 긴 다문 입 구간이 아닌 곳
    voiced = [True] * L
    i = 0
    while i < L:
        if nib[i] == 6:
            j = i
            while j < L and nib[j] == 6:
                j += 1
            if j - i >= SILENT_RUN:
                for f in range(i, j):
                    voiced[f] = False
            i = j
        else:
            i += 1
    for f in marks:
        voiced[f] = True

    visible = [i for i, c in enumerate(ko_chars) if c != '⁣']
    pads = [i for i, c in enumerate(ko_chars) if c == '⁣']
    ko = [ko_chars[i] for i in visible]
    jt = marks + [L]

    def jtime(idx):
        return jt[idx]

    nj = len(jp_chars)
    # 원문 글자별 발화 길이(뒤에 붙은 긴 무음 제외)
    dur = []
    for j in range(nj):
        e = jt[j + 1]
        while e > marks[j] + 1 and not voiced[e - 1]:
            e -= 1
        dur.append(max(1, e - marks[j]))

    def jpos_time(p):
        """원문 글자 위치(소수)를 프레임으로: 글자 안에서는 그 글자의 발화 구간을 비례로 나눈다."""
        j = min(int(p), nj - 1)
        return marks[j] + int((p - j) * dur[j])

    # 기준점: (한글 순번, 원문 위치, 앞 구간이 끝나는 원문 위치)
    anchors = [(0, 0.0, 0.0)]
    vis_index = {orig: v for v, orig in enumerate(visible)}
    kg = groups(ko)
    inside = {i for _, c, d in kg for i in range(c, d + 1)}
    kg += [('space', v + 1, v + 1) for v in (vis_index.get(i) for i in ko_spaces)
           if v is not None and v + 1 < len(ko) and v + 1 not in inside and v not in inside]
    kg.sort(key=lambda g: (g[1], g[2]))
    for (k1, a, b), (kk, c, d) in match(groups(jp_chars), kg, nj, len(ko)):
        for t in range(d - c):
            jp = float(min(a + t, b - 1))
            anchors.append((c + t, jp, jp))
        # 띄어쓰기로 맞춘 경계: 앞 글자들은 원문 문장부호 앞에서 끝낸다
        anchors.append((d, float(b), float(a) if kk == 'space' else float(b)))
    anchors.append((len(ko), float(nj), float(nj)))
    anchors.sort()
    uniq = []
    for c, j, cut in anchors:
        if uniq and c == uniq[-1][0]:
            continue
        if uniq and j < uniq[-1][1]:
            j = uniq[-1][1]
        uniq.append((c, j, max(min(cut, j), uniq[-1][1] if uniq else 0.0)))
    # 기준점 사이 한글 글자는 원문 글자 위치에 비례해 대응시킨다
    # (예: 「제국화격단・장미조」의 7번째 「장」은 「帝国華撃団・薔薇組」의 7번째 「薔」 시점)
    pos = [None] * len(ko)
    for (c0, j0, _), (c1, j1, cut) in zip(uniq, uniq[1:]):
        n = c1 - c0
        for t in range(n):
            if c0 + t < len(ko):
                pos[c0 + t] = jpos_time(j0 + t * (cut - j0) / n)
    for t in range(len(ko)):
        if pos[t] is None:
            pos[t] = pos[t - 1] + 1 if t else marks[0]

    full = [None] * len(ko_chars)
    for i, f in zip(visible, pos):
        full[i] = f
    for i, f in zip(pads, range(L - len(pads), L)):
        full[i] = f
    last = -1
    for i in range(len(full)):
        full[i] = max(full[i], last + 1)
        last = full[i]
    if last >= L:
        nxt = L
        for i in range(len(full) - 1, -1, -1):
            full[i] = min(full[i], nxt - 1)
            nxt = full[i]
        if full[0] < 0:
            return None
    out = list(nib)
    for i in marks:
        j = i + 1
        while j < L and nib[j] == 7:
            j += 1
        out[i] = nib[j] if j < L else 6
    for f in full:
        out[f] = 7
    return pack(out)

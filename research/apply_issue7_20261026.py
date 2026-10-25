"""이슈 #7 본문에 추가된 대사 제안 2건(요키히코·카야마)을 반영한다."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from apply_dialogue_review import apply

plan = {
    'dialogue:f1be4c5acb86c0ca': {
        'text': '알았어요，코토 님∈//자…다들 괜찮아？//피난처까지 달릴 수 있어？',
        'reason': '이슈 #7: 「アナタたち」 번역 누락 → 「다들」(대사 칸 60바이트)',
    },
    'dialogue:131bd6d7a096c0c5': {
        'text': '윽…겁…겁먹지 마라∈//응전하라∈',
        'reason': '이슈 #7: 「ひるむな」 「주춤하지 마라」 → 「겁먹지 마라」(「뭇」은 글꼴에 없음)',
    },
}
reviews = {k: {'status': 'approved', 'note': v['reason']} for k, v in plan.items()}
apply('20261026-claude-issue7-lines', plan, reviews)

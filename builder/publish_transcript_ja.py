"""publish_transcript_ja.py — render a reviewed Japanese press-conference transcript
(markdown) as a free page on the public site. Path C: the text is Takuji's reviewed
draft, carried over unchanged; this script only re-skins it.

    python builder/publish_transcript_ja.py --check   # gates only, writes nothing
    python builder/publish_transcript_ja.py           # gates, then writes the page

First use: Governor Ueda's press conference of 18 September 2026 (the draft in the
report's drafts folder on the JMA drive, reviewed by Takuji on 2026-09-19).

Every structural rule asserts its own match count, so a transcript in a different
shape stops the publish instead of shipping a page this script no longer understands.
The paid-subscription card is copied from a delivered free page, not re-authored,
so it cannot drift from the site-wide wording.
"""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- page settings
SRC = (r'G:\My Drive\JMA drive\Research2026\reports\2026-09\2026-09-19-ueda-presser-transcript'
       r'\drafts\2026-09-19-ueda-presser-transcript-ja-v03-takuji.md')
SLUG = '2026-09-18-boj-ueda-presser-transcript'
VIDEO_ID = 'DpxsNUutPi4'
POST_URL = 'https://takujiokubo.substack.com/p/boj-ueda-virtually-no-chance-of-an'
DATE_EN = '18 September 2026'
TITLE_JA = '植田総裁 記者会見（2026年9月18日）'   # "文字起こし" dropped at Takuji's request, 2026-09-19
TITLE_EN = "Governor Ueda's press conference, 18 September 2026: Japanese transcript"
NOTICE_EN = ("This is an unofficial transcript prepared by Japan Macro Advisors. Once the Bank of Japan "
             "publishes its official transcript, expected on 24 September, please refer to that instead.")
NOTICE_JA = ("本稿はJapan Macro Advisorsによる非公式の文字起こしです。日本銀行が公式の記者会見要旨を"
             "公表した後（9月24日の予定）は、そちらをご参照ください。")
PERK_FROM = os.path.join(REPO, '2026-08-21-canada-gross-net', 'index.html')   # disclaimer source
# Page-specific subscription card (Takuji, 2026-09-19): BoJ-PSI as the main attraction,
# the JGB yield-curve model second, in the JMA Database page's own descriptions. Keeps the
# site card's headline, classes and Subscribe link; the shared builder card is unchanged.
SUBSCRIBE_URL = 'https://takujiokubo.substack.com/subscribe'
PERK = (
    '<div class="perkbox">\n'
    '  <h3>Paid subscribers get the JMA Database</h3>\n'
    '  <ul class="perklist">\n'
    '    <li><strong>BoJ Policy Stance Indicator</strong>: where each board member stands on the economy, '
    'inflation and the policy rate, scored at every policy meeting.</li>\n'
    '    <li><strong>JGB yield-curve model</strong>: our policy-rate path and yield forecasts, with yields '
    'split into expectations and term premia, monthly from 2002 to 2029.</li>\n'
    '  </ul>\n'
    '  <p class="perk">Plus the BoJ-QT progress monitor and global FX reserves back to 1980.</p>\n'
    f'  <a class="btn" href="{SUBSCRIBE_URL}">Subscribe</a>\n'
    '  </div>')
N_QUESTIONS = 25
SPEAKERS = {'植田総裁', '質問', '司会', '幹事社'}


def ts_link(m):
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    sec = h * 3600 + mi * 60 + s
    return (f'<a class="ts" href="https://www.youtube.com/watch?v={VIDEO_ID}&amp;t={sec}s">'
            f'{m.group(1)}:{m.group(2)}:{m.group(3)}</a>')


TS = re.compile(r'［(\d+):(\d\d):(\d\d)］')


def render(md):
    lines = md.split('\n')
    # the draft's own header (title, date, note, video line) ends at the first rule
    first_rule = lines.index('---')
    body = [l for l in lines[first_rule + 1:] if l.strip() != '---']
    out, paras, speaker = [], [], None
    counts = {'h2': 0, 'h3': 0, 'label': 0, 'cont': 0}
    for l in body:
        if not l.strip():
            continue
        if l.startswith('### '):
            m = re.match(r'### (質問\d+(?:（幹事社）)?)［(\d+):(\d\d):(\d\d)］: (.+)$', l)
            assert m, l
            t = TS.sub(ts_link, f'［{m.group(2)}:{m.group(3)}:{m.group(4)}］')
            out.append(f'<h3><span class="qn">{html.escape(m.group(1))}</span> {t}<br>'
                       f'<span class="qt">{html.escape(m.group(5))}</span></h3>')
            counts['h3'] += 1
            speaker = None
        elif l.startswith('## '):
            m = re.match(r'## ([^［]+)(?:［(\d+):(\d\d):(\d\d)］)?$', l)
            assert m, l
            t = (' ' + TS.sub(ts_link, f'［{m.group(2)}:{m.group(3)}:{m.group(4)}］')) if m.group(2) else ''
            out.append(f'<h2>{html.escape(m.group(1))}{t}</h2>')
            counts['h2'] += 1
            speaker = None
        elif l.startswith('**'):
            m = re.match(r'\*\*([^*]+)\*\*(?:［(\d+):(\d\d):(\d\d)］)?: (.+)$', l)
            assert m and m.group(1) in SPEAKERS, l
            speaker = m.group(1)
            t = (' ' + TS.sub(ts_link, f'［{m.group(2)}:{m.group(3)}:{m.group(4)}］')) if m.group(2) else ''
            cls = {'植田総裁': 'a', '質問': 'q', '司会': 'mod', '幹事社': 'mod'}[speaker]
            out.append(f'<p class="{cls}"><strong>{html.escape(speaker)}</strong>{t}'
                       f'：{html.escape(m.group(5))}</p>')
            paras.append(m.group(5))
            counts['label'] += 1
        else:
            assert speaker, ('continuation paragraph with no speaker', l)
            assert not l.startswith(('#', '>', '*')), l
            cls = {'植田総裁': 'a', '質問': 'q', '司会': 'mod', '幹事社': 'mod'}[speaker]
            out.append(f'<p class="{cls} cont">{html.escape(l)}</p>')
            paras.append(l)
            counts['cont'] += 1
    return '\n'.join(out), paras, counts


CSS = """
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'PT Serif',Georgia,serif;background:#FCFBF8;color:#2a2a28;
       line-height:1.7;padding:40px 20px 80px;max-width:880px;margin:0 auto}
  a{color:#3b65a2;text-decoration:none}
  a:hover{color:#2c4d7e;text-decoration:underline}
  .text{max-width:680px;margin-left:auto;margin-right:auto}
  .mrow{display:flex;justify-content:space-between;align-items:flex-end;
        padding-bottom:12px;border-bottom:2px solid #1c1c1c}
  .mrow img{height:24px;width:auto;display:block;flex:none}
  .mdate{font:400 12px 'Public Sans',sans-serif;color:#737373}
  .mrow2{display:flex;justify-content:space-between;align-items:baseline;padding-top:6px}
  .tagline{font:italic 400 12px 'PT Serif',serif;color:#8a8a82}
  .slabel{font:600 10.5px 'Public Sans',sans-serif;letter-spacing:1.6px;
          color:#a08a5f;text-transform:uppercase}
  .banner{background:#f2f1ec;border:1px solid #e2e0d8;padding:11px 18px;
          margin:22px auto 0;max-width:680px;
          font:400 13px/1.6 'Public Sans',sans-serif;color:#54544e}
  .banner p+p{margin-top:6px}
  .btn{display:inline-block;margin-top:12px;background:#3b65a2;color:#fff;
       font:600 14px 'Public Sans',sans-serif;text-decoration:none;
       padding:9px 16px;border-radius:4px}
  .btn:hover{background:#2c4d7e;color:#fff;text-decoration:none}
  .perkbox{margin:18px 0 0;border:1px solid #3b65a2;border-left:5px solid #3b65a2;
           background:#f4f6fa;padding:20px 24px}
  .perkbox h3{margin:0 0 6px;font:700 20px/1.3 'PT Serif',serif;color:#3b65a2}
  .perkbox .perk{margin:0;font:400 15.5px/1.6 'Public Sans',sans-serif;color:#2c2c2a}
  .perkbox .btn{margin-top:14px;font-size:15px;padding:11px 22px}
  .perkbox.end{margin-top:56px}
  .perkbox .perklist{margin:4px 0 10px 20px;font:400 15.5px/1.6 'Public Sans',sans-serif;color:#2c2c2a}
  .perkbox .perklist li{margin:0 0 6px}
  .perkbox .perklist strong{font-weight:600;color:#1c1c1c}
  .more-articles{margin:14px auto 0;max-width:680px;
       font:400 13.5px 'Public Sans',sans-serif;color:#54544e}
  header{margin-top:36px}
  header h1{font:700 30px/1.35 'PT Serif','Hiragino Mincho ProN','Yu Mincho',serif;
            color:#1c1c1c;margin:0 0 10px}
  header .en{font:400 16px/1.5 'PT Serif',serif;color:#54544e;margin:0 0 12px}
  header .meta{font:400 13px 'Public Sans',sans-serif;color:#737373;margin-bottom:6px}
  .ja{font-family:'Hiragino Kaku Gothic ProN','Hiragino Sans','Yu Gothic','Meiryo',sans-serif;
      font-size:16px;line-height:1.95;color:#2a2a28}
  .ja h2{font:700 22px/1.4 'Hiragino Mincho ProN','Yu Mincho','PT Serif',serif;color:#1c1c1c;
         margin:52px 0 14px;border-top:2px solid #1c1c1c;padding-top:14px}
  .ja h3{font:700 17px/1.5 'Hiragino Kaku Gothic ProN','Yu Gothic','Meiryo',sans-serif;
         color:#1c1c1c;margin:40px 0 10px}
  .ja h3 .qt{font-weight:400;color:#54544e;font-size:15.5px}
  .ja p{margin:0 0 14px}
  .ja p.q{background:#f2f1ec;border-left:3px solid #c9c6ba;padding:10px 14px;color:#3d3d39}
  .ja p.q.cont{margin-top:-14px;padding-top:0}
  .ja p.mod{font-size:14px;color:#737373}
  .ja strong{font-weight:700}
  a.ts{font:500 12.5px 'Public Sans',sans-serif;color:#3b65a2;white-space:nowrap}
  .disclaimer{font:400 10.5px/1.55 'Public Sans',sans-serif;color:#9a9a92;
              margin:14px auto 0;max-width:680px}
  .nav{font:400 12px 'Public Sans',sans-serif;color:#9a9a92;margin:10px auto 0;max-width:680px}
  @media(max-width:640px){
    body{padding:24px 12px 48px}
    header h1{font-size:23px}
    .ja{font-size:15.5px}
  }
"""


def main():
    check = '--check' in sys.argv
    md = open(SRC, encoding='utf-8').read()
    body_html, paras, counts = render(md)

    canada = open(PERK_FROM, encoding='utf-8').read()
    perk = PERK
    disc = re.findall(r'<p class="disclaimer">.*?</p>', canada, re.S)
    assert len(disc) == 1, len(disc)

    page = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(TITLE_JA)} | Japan Macro Advisors</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Serif:ital,wght@0,400;0,700;1,400;1,700&amp;family=Public+Sans:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="text" lang="en">
  <div class="mrow">
    <img src="../assets/jma-logo.png" alt="Japan Macro Advisors">
    <span class="mdate">{DATE_EN}</span>
  </div>
  <div class="mrow2">
    <span class="tagline">Unbiased Opinion on Japan&rsquo;s Economy</span>
    <span class="slabel">Transcript</span>
  </div>
</div>

<div class="banner top">
  <p lang="en">{html.escape(NOTICE_EN)}</p>
  <p>{html.escape(NOTICE_JA)}</p>
</div>

<header class="text">
  <h1>{html.escape(TITLE_JA)}</h1>
  <p class="en" lang="en">{html.escape(TITLE_EN)}</p>
  <div class="meta" lang="en"><a href="{POST_URL}">Read the article</a> · <a href="https://www.youtube.com/watch?v={VIDEO_ID}">Watch the press conference</a> (Bank of Japan, YouTube). Each time stamp links to that point in the video.</div>
  <div lang="en">
  {perk}
  </div>
</header>

<article class="text ja">
{body_html}
</article>

<div class="text" lang="en">
  {perk.replace('class="perkbox"', 'class="perkbox end"', 1)}
</div>
<p class="more-articles" lang="en">More articles: <a href="https://takujiokubo.substack.com">takujiokubo.substack.com</a></p>
{disc[0].replace('<p class="disclaimer">', '<p class="disclaimer" lang="en">', 1)}
<p class="nav" lang="en"><a href="https://takujiokubo.substack.com">takujiokubo.substack.com</a></p>
</body>
</html>
"""

    # ------------------------------------------------------------ gates
    G = []

    def gate(name, ok, detail=''):
        G.append((name, bool(ok), detail))

    q_heads = re.findall(r'^### 質問\d+', md, re.M)
    gate('source has 25 question headings', len(q_heads) == N_QUESTIONS, len(q_heads))
    gate('page has 25 question headings', page.count('<span class="qn">') == N_QUESTIONS, page.count('<span class="qn">'))
    gate('page has 3 section headings', counts['h2'] == 3 and page.count('<h2>') == 3,
         f"{counts['h2']} rendered (冒頭, 総裁冒頭説明, 質疑応答; the draft's date line is header)")
    # every paragraph of the reviewed text appears on the page, in order, unchanged
    text = html.unescape(re.sub(r'<[^>]+>', '', body_html))
    pos, missing = 0, []
    for p in paras:
        i = text.find(p, pos)
        if i < 0:
            missing.append(p[:30])
        else:
            pos = i + len(p)
    gate('every reviewed paragraph present, in order, verbatim', not missing and len(paras) > 70,
         f'{len(paras)} paragraphs, {len(missing)} missing')
    src_chars = sum(len(p) for p in paras)
    gate('no text added inside the transcript', len(re.sub(r'\s', '', text)) - src_chars < 3000,
         f'body text {len(text)} chars vs {src_chars} paragraph chars (difference = speaker labels, headings, timestamps)')
    n_ts_src = len(TS.findall(md))
    n_links = page.count('class="ts"')
    gate('every timestamp became a video link', n_links == n_ts_src and n_ts_src > 25,
         f'{n_links} links / {n_ts_src} timestamps')
    gate('subscription card present twice (top and end)',
         page.count('Paid subscribers get the JMA Database') == 2 and page.count('class="perkbox') == 2, '')
    li = re.findall(r'<li><strong>([^<]+)</strong>', page)
    gate('card leads with BoJ-PSI, then the yield-curve model (both cards)',
         li == ['BoJ Policy Stance Indicator', 'JGB yield-curve model'] * 2, li)
    gate('headline without 文字起こし', '<h1>植田総裁 記者会見（2026年9月18日）</h1>' in page
         and '文字起こし（2026' not in page, '')
    gate('notice present (EN and JA)', NOTICE_EN.split('.')[0] in page and '非公式の文字起こし' in page, '')
    gate('article link present', page.count(POST_URL) == 1, '')
    # absence gates
    for bad in ('〔', '字幕', 'free to use and reproduce', 'Download', '.csv', 'Whisper', '機械',
                '毎日新聞', '朝日新聞', '日経', 'ロイター', 'ブルームバーグ', '時事通信', '共同通信', '読売'):
        gate(f'absent: {bad}', bad not in page, page.count(bad))

    w = max(len(n) for n, _, _ in G)
    for n, ok, d in G:
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {d}")
    if not all(ok for _, ok, _ in G):
        sys.exit('gates failed — nothing written')
    if check:
        print('--check: all gates pass, nothing written')
        return
    d = os.path.join(REPO, SLUG)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8', newline='\n').write(page)
    print('written', os.path.join(d, 'index.html'), len(page.encode('utf-8')), 'bytes')


if __name__ == '__main__':
    main()

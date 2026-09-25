import json
from pathlib import Path
p=Path('captures/mines-search/seed-14.json')
d=json.loads(p.read_text(encoding='utf8'))
assert d['baseline']['events'][0]['before']==d['shaped']['events'][0]['before']==d['opening']['initial']
for side in ['baseline','shaped']:
    previous=d['opening']['initial']
    for e in d[side]['events']:
        assert e['before']==previous
        assert e['answer']['answers']['kind']['choice']==e['action']['kind']
        previous=e['after']
d['selection']={'purpose':'Selected illustration, not a benchmark','criterion':'First baseline run with at least 10 actions among seeds 11-40','attempts':json.loads(Path('captures/mines-search/summary.json').read_text())}
root=Path('showcase/jev-games')
(root/'traces/minesweeper-pair.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
(root/'traces/minesweeper-pair.js').write_text('window.MINESWEEPER_PAIR = '+json.dumps(d,ensure_ascii=False)+';',encoding='utf8')
p=root/'minesweeper.html'
s=p.read_text(encoding='utf8')
s=s.replace('minesweeper-pair.js?v=pair1','minesweeper-pair.js?v=seed14').replace('minesweeper-pair-loader.js?v=pair1','minesweeper-pair-loader.js?v=seed14').replace('minesweeper.js?v=pair1','minesweeper.js?v=seed14')
s=s.replace('真实请求只提供当前可见棋盘和可翻开的未知格，没有确定雷和风险排序。','真实 Jev 根据可见数字选择翻格、插旗或撤旗；不提供程序推导的确定线索。')
s=s.replace('两边都是固定的真实 Jev trace，页面播放不会重新调用 API。','同一雷盘、同一程序开局。原始版 10 次决策后踩雷；约束版 54 次决策通关。此局从 4 张测试盘中选作演示，不代表平均胜率。回放不调用 API。')
p.write_text(s,encoding='utf8')
print('Published verified pair: baseline 10 / shaped 54')

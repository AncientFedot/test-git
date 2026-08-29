from pathlib import Path

p = Path('app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java')
s = p.read_text(encoding='utf-8')

bad = r'rawId.matches("\d+")'
good = r'rawId.matches("\\d+")'
count = s.count(bad)
if count != 1:
    raise SystemExit(f'Expected exactly one Java regex escape defect, found {count}')
s = s.replace(bad, good, 1)
p.write_text(s, encoding='utf-8')
print('V3G compile escape fix OK: Java regex now uses \\d+')

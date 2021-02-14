pyinstaller TEAPTracker_console.spec
md dist\TEAPTracker\tld\res
copy "venv\Lib\site-packages\tld\res\effective_tld_names.dat.txt" dist\TEAPTracker\tld\res
copy "TEAPCTGData.csv" dist\TEAPTracker
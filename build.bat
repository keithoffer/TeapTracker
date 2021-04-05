pyinstaller TEAPTracker_console.spec
md dist\TEAPTracker\tld\res
md dist\TEAPTracker\resources
copy "venv\Lib\site-packages\tld\res\effective_tld_names.dat.txt" dist\TEAPTracker\tld\res
copy "TEAPCTGData.csv" dist\TEAPTracker
copy "resources\CTG v3.6 Progression Monitor Tool.xlsx" "dist\TEAPTracker\resources\CTG v3.6 Progression Monitor Tool.xlsx"
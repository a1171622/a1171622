#!/usr/bin/env bash
# 26016 v20 export pipeline (read-only on 26016_check_v20.cdb / .erg). Same scripts as the v19m export, paths moved to v20.
set -e
E="/c/Sofistik workflow/26016-design-report/v20_export"
CDB='C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.cdb'
DAT='C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.dat'
cd "$E/scripts"
echo "== erg.py";            py -3.11 erg.py
echo "== make_model_json";   py -3.11 make_model_json.py
echo "== extract_v20";      py -3.11 extract_v20.py "C:\\Sofistik workflow\\26016-design-report\\v20_export"
echo "== l1_detail";         py -3.11 l1_detail.py "$CDB" "$DAT" erg_parsed.json "C:\\Sofistik workflow\\26016-design-report\\v20_export\\l1_detail_v20.json"
echo "== draw_reading";      py -3.11 draw_reading.py "C:\\Sofistik workflow\\26016-design-report\\v20_export"
cd "$E/A_followup/scripts"
cp ../../scripts/erg_parsed.json .
export PYTHONPATH="$E/scripts"
echo "== survey";            py -3.11 survey.py > survey.txt
echo "== partA";             py -3.11 partA.py  > partA1.txt
echo "== partA2";            py -3.11 partA2.py > partA2.txt
echo "== partA3";            py -3.11 partA3.py > partA3.txt
echo "== draw";              py -3.11 draw.py
mv -f partA1.json partA2.json partA3.json A_followup_reading.png ..
echo done

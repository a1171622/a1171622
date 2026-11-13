#!/usr/bin/env bash
# 26016 v21 export pipeline (read-only on 26016_check_v21.cdb / .erg). Same scripts as the v20 export, paths moved to v21.
set -e
E="/c/Sofistik workflow/26016-design-report/v21_export"
CDB='C:\Sofistik workflow\26016-member-check\v21\26016_check_v21.cdb'
DAT='C:\Sofistik workflow\26016-member-check\v21\26016_check_v21.dat'
cd "$E/scripts"
echo "== erg.py";            py -3.11 erg.py
echo "== make_model_json";   py -3.11 make_model_json.py
echo "== extract_v21";      py -3.11 extract_v21.py "C:\\Sofistik workflow\\26016-design-report\\v21_export"
echo "== l1_detail";         py -3.11 l1_detail.py "$CDB" "$DAT" erg_parsed.json "C:\\Sofistik workflow\\26016-design-report\\v21_export\\l1_detail_v21.json"
echo "== draw_reading";      py -3.11 draw_reading.py "C:\\Sofistik workflow\\26016-design-report\\v21_export"
cd "$E/A_followup/scripts"
cp ../../scripts/erg_parsed.json .
export PYTHONPATH="$E/scripts"
echo "== survey";            py -3.11 survey.py > survey.txt
echo "== partA";             py -3.11 partA.py  > partA1.txt
echo "== partA2";            py -3.11 partA2.py > partA2.txt
echo "== partA3";            py -3.11 partA3.py > partA3.txt
echo "== draw";              py -3.11 draw.py
echo "== buckling_g62";     py -3.11 buckling_g62.py > buckling_g62.txt
mv -f partA1.json partA2.json partA3.json A_followup_reading.png ..
cd "$E/A_followup"
echo "== part_a_md";         py -3.11 scripts/part_a_md.py
cd "$E/scripts"
echo "== make_results";      py -3.11 make_results.py run_checks.json
echo "== results_extra";     py -3.11 results_extra_v21.py
echo done

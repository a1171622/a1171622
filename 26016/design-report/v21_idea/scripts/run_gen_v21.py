import glob, subprocess, sys
files = sorted(glob.glob(r"C:\Sofistik workflow\idea-statica\v21\xml_*\*.ideaCon"))
print(len(files), flush=True)
sys.exit(subprocess.call(["py", "-3.15", r"C:\Sofistik workflow\idea-statica\26016_IDEA_appendix\scripts\gen_reports2.py",
    r"C:\Sofistik workflow\idea-statica\26016_IDEA_appendix\projects_v21", r"C:\Sofistik workflow\idea-statica\26016_IDEA_appendix\reports_v21"] + files))
